import os
import signal
import sys
import time
from pathlib import Path

# Foreign Vulkan windows can be embedded by Qt's xcb backend, including on KDE
# Wayland through XWayland. Explicit platform overrides (e.g. tests) are retained.
if os.environ.get('DISPLAY'):
    os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from PySide6.QtCore import QLocale, QPoint, QPointF, QRectF, QSettings, QSize, QTimer, Qt, QUrl, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainterPath, QDesktopServices, QIcon, QLinearGradient, QPainter, QPalette, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QLayout, QButtonGroup, QCheckBox, QComboBox,
                               QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QMenu, QWidgetAction,
                               QLabel, QLineEdit, QPlainTextEdit, QFileDialog, QColorDialog, QPushButton, QScrollArea, QSplitter,
                               QVBoxLayout, QWidget, QListView, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QStyleOptionComboBox, QStyleOptionFrame, QStylePainter, QGraphicsOpacityEffect)
from .animation import ButtonGlow, ButtonMotion, PageMotion
from . import mangohud, layer_order
from .panels import FrostedPanel
from .preview import Preview
from .notifications import Notification, ElidedLabel
from .runtime import available as textured_runtime_available


class PopupDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option)
        option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


class NoWheelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setItemDelegate(PopupDelegate(view))
        view.setFrameShape(QFrame.NoFrame)
        self.setView(view)
        self.view().window().setObjectName("comboPopup")

    def wheelEvent(self, event):
        event.ignore()


class ApplicationComboBox(NoWheelComboBox):
    def paintEvent(self, event):
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        text = option.currentText
        name, separator, pid = text.rpartition(' · PID ')
        pid_text = f'· PID {pid}' if separator else ''
        text = name if separator else text
        option.currentText = ''
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        rect = self.style().subControlRect(QStyle.CC_ComboBox, option,
                                           QStyle.SC_ComboBoxEditField, self)
        # The stylesheet already reserves the arrow width; the style's edit
        # rectangle can subtract it again. Use the available space up to it.
        arrow = self.style().subControlRect(QStyle.CC_ComboBox, option,
                                            QStyle.SC_ComboBoxArrow, self)
        rect.setRight(arrow.left() - 6)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        if pid_text:
            pid_width = self.fontMetrics().horizontalAdvance(pid_text)
            pid_rect = QRectF(rect.right() - pid_width + 1, rect.top(), pid_width, rect.height())
            painter.setPen(self.palette().color(QPalette.Text))
            painter.drawText(pid_rect, Qt.AlignRight | Qt.AlignVCenter, pid_text)
            rect.setRight(round(pid_rect.left()) - 5)
        scale = self.devicePixelRatioF()
        layer = QPixmap(round(rect.width() * scale), round(rect.height() * scale))
        layer.setDevicePixelRatio(scale)
        layer.fill(Qt.transparent)
        text_painter = QPainter(layer)
        text_painter.setFont(self.font())
        text_painter.setPen(self.palette().color(QPalette.Text))
        text_painter.drawText(0,
                              0, rect.width(), rect.height(),
                              Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, text)
        if self.fontMetrics().horizontalAdvance(text) > rect.width():
            fade = QLinearGradient(max(0, rect.width() - 32), 0, rect.width(), 0)
            fade.setColorAt(0, QColor(0, 0, 0, 255))
            fade.setColorAt(1, QColor(0, 0, 0, 0))
            text_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            text_painter.fillRect(0, 0, rect.width(), rect.height(), fade)
        text_painter.end()
        painter.drawPixmap(rect.topLeft(), layer)


class PathEdit(QLineEdit):
    def paintEvent(self, event):
        if self.hasFocus() or not self.text():
            super().paintEvent(event)
            return
        painter = QStylePainter(self)
        option = QStyleOptionFrame()
        self.initStyleOption(option)
        painter.drawPrimitive(QStyle.PE_PanelLineEdit, option)
        rect = self.rect().adjusted(11, 1, -11, -1)
        scale = self.devicePixelRatioF()
        layer = QPixmap(round(rect.width() * scale), round(rect.height() * scale))
        layer.setDevicePixelRatio(scale)
        layer.fill(Qt.transparent)
        text = QPainter(layer)
        text.setFont(self.font())
        text.setPen(self.palette().color(QPalette.Text))
        overflow = self.fontMetrics().horizontalAdvance(self.text()) > rect.width()
        alignment = Qt.AlignRight if overflow else Qt.AlignLeft
        text.drawText(0, 0, rect.width(), rect.height(), alignment | Qt.AlignVCenter, self.text())
        if overflow:
            fade = QLinearGradient(0, 0, 30, 0)
            fade.setColorAt(0, QColor(0, 0, 0, 0))
            fade.setColorAt(1, QColor(0, 0, 0, 255))
            text.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            text.fillRect(0, 0, rect.width(), rect.height(), fade)
        text.end()
        painter.drawPixmap(rect.topLeft(), layer)


class NoWheelSpinBox(QDoubleSpinBox):
    def focusInEvent(self, event):
        container = getattr(self, 'editing_container', None)
        if container is not None:
            container.set_editing(True)
        self.display_suffix = self.suffix()
        self.display_special = self.specialValueText()
        self.setSuffix('')
        self.setSpecialValueText('')
        super().focusInEvent(event)
        self.selectAll()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        container = getattr(self, 'editing_container', None)
        if container is not None:
            container.set_editing(False)
        self.setSuffix(getattr(self, 'display_suffix', self.suffix()))
        self.setSpecialValueText(getattr(self, 'display_special', self.specialValueText()))

    def stepBy(self, steps):
        super().stepBy(steps)
        self.lineEdit().deselect()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.clearFocus()

    def wheelEvent(self, event):
        event.ignore()


class DependencyRow(QWidget):
    def __init__(self, parent_option, child_option):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 0, 0)
        layout.addWidget(child_option)
        parent_option.toggled.connect(self.set_available)
        self.set_available(parent_option.isChecked())

    def set_available(self, available):
        self.setEnabled(available)
        self.setStyleSheet('QCheckBox:disabled { color: #686868; }')
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#5c5c5c'), 1))
        center = self.height() // 2
        painter.drawLine(7, 0, 7, center)
        painter.drawLine(7, center, 21, center)


class NumberControl(QFrame):
    """Shared minus/value/plus control for every numeric setting."""
    def __init__(self, field):
        super().__init__()
        self.setObjectName('fpsControl')
        self.edit_amount = 0.
        self.edit_motion = QVariantAnimation(self)
        self.edit_motion.setDuration(240)
        self.edit_motion.setEasingCurve(QEasingCurve.OutCubic)
        self.edit_motion.valueChanged.connect(self.set_edit_amount)
        self.setFixedHeight(36)
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        field.setMinimumWidth(0)
        field.setAlignment(Qt.AlignCenter)
        self.down = QPushButton('−')
        self.up = QPushButton('+')
        for button, direction, action in ((self.down, 'Decrease', field.stepDown),
                                          (self.up, 'Increase', field.stepUp)):
            button.setObjectName('fpsStep')
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoDefault(False)
            button.setFixedSize(36, 32)
            button.setAccessibleName(f'{direction} {field.accessibleName()}')
            button.setAutoRepeat(True)
            button.clicked.connect(action)
        def separator():
            line = QFrame()
            line.setObjectName('fpsSeparator')
            line.setFixedSize(1, 18)
            return line
        row.addWidget(self.down)
        row.addWidget(separator())
        row.addWidget(field, 1)
        row.addWidget(separator())
        row.addWidget(self.up)
        field.editing_container = self


    def set_edit_amount(self, value):
        self.edit_amount = float(value)
        self.update()

    def set_editing(self, active):
        self.edit_motion.stop()
        if active:
            self.set_edit_amount(1.)
        else:
            self.edit_motion.setStartValue(self.edit_amount)
            self.edit_motion.setEndValue(0.)
            self.edit_motion.start()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.edit_amount <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self.edit_amount)
        painter.setPen(QPen(QColor('#484848'), 1))
        painter.setBrush(QColor('#242424'))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 5, 5)


class ScrollFade(QWidget):
    def __init__(self, parent, top=False):
        super().__init__(parent)
        self.top = top
        self.amount = 0.
        self.present = False
        self.dot_opacity = 1.
        self.pulse = QVariantAnimation(self)
        self.pulse.setDuration(1800)
        self.pulse.setStartValue(1.)
        self.pulse.setKeyValueAt(.5, .35)
        self.pulse.setEndValue(1.)
        self.pulse.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse.setLoopCount(-1)
        self.pulse.valueChanged.connect(self.set_dot_opacity)
        self.motion = QVariantAnimation(self)
        self.motion.setDuration(260)
        self.motion.setEasingCurve(QEasingCurve.OutCubic)
        self.motion.valueChanged.connect(self.set_amount)
        self.motion.finished.connect(self.finish_transition)
        self.hide()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)

    def set_dot_opacity(self, value):
        self.dot_opacity = float(value)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self.present:
            self.pulse.start()

    def hideEvent(self, event):
        self.pulse.stop()
        super().hideEvent(event)

    def set_amount(self, amount):
        self.amount = float(amount)
        self.update()

    def finish_transition(self):
        if not self.present:
            self.hide()

    def set_present(self, present):
        if self.present == present:
            return
        self.present = present
        self.motion.stop()
        self.show()
        self.motion.setStartValue(self.amount)
        self.motion.setEndValue(1. if present else 0.)
        self.motion.start()

    def paintEvent(self, event):
        gradient = QLinearGradient(0, self.height() if self.top else 0,
                                   0, 0 if self.top else self.height())
        gradient.setColorAt(0, QColor(24, 24, 24, 0))
        gradient.setColorAt(1, QColor(24, 24, 24, 255))
        painter = QPainter(self)
        painter.setOpacity(self.amount)
        painter.fillRect(self.rect(), gradient)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setOpacity(self.amount * self.dot_opacity)
        painter.setBrush(QColor('#929292'))
        y = 7 if self.top else self.height() - 7
        for offset in (-6, 0, 6):
            painter.drawEllipse(QPointF(self.width() / 2 + offset, y), 1.5, 1.5)



class SettingsScroll(QScrollArea):
    def __init__(self):
        super().__init__()
        self.viewport().setAutoFillBackground(False)
        self.fade = ScrollFade(self.viewport())
        self.top_fade = ScrollFade(self.viewport(), top=True)
        self.verticalScrollBar().rangeChanged.connect(self.update_fade)
        self.verticalScrollBar().valueChanged.connect(self.update_fade)

    def update_fade(self, *_):
        viewport = self.viewport()
        self.fade.setGeometry(0, max(0, viewport.height() - 48), viewport.width(), 48)
        self.fade.set_present(self.verticalScrollBar().value() < self.verticalScrollBar().maximum())
        self.fade.raise_()
        self.top_fade.setGeometry(0, 0, viewport.width(), 48)
        self.top_fade.set_present(self.verticalScrollBar().value() > self.verticalScrollBar().minimum())
        self.top_fade.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_fade()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Vela')
        self.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/vela.svg')))
        self.setMinimumSize(1060, 600)
        self.resize(1400, 780)
        palette = self.palette()
        for role, color in (
            (QPalette.Window, '#0f0f0f'), (QPalette.Base, '#1a1a1a'),
            (QPalette.Button, '#1a1a1a'), (QPalette.Text, '#f5f5f5'),
            (QPalette.WindowText, '#f5f5f5'), (QPalette.ButtonText, '#f5f5f5'),
            (QPalette.Highlight, '#246bce'), (QPalette.HighlightedText, '#ffffff'),
            (QPalette.Light, '#444444'), (QPalette.Mid, '#333333'),
            (QPalette.Dark, '#080808'),
        ):
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setObjectName('velaWindow')
        self.setStyleSheet("""
            QWidget { font-family: 'Noto Sans'; font-size: 13px; color: #dddddd; }
            QWidget#velaWindow { background: transparent; }
            QWidget#sidebar { background: transparent; border: none; }
            QWidget#settingsContent { background: transparent; }
            QLabel { background: transparent; }
            QFrame#previewSettings { background: #181818; border: 1px solid #383838; border-radius: 8px; }
            QPushButton#helpIcon { min-height: 0; padding: 0; border-radius: 14px; font-size: 15px; color: #dddddd; background: transparent; border: 1px solid #484848; }
            QLabel#panelTitle { color: #eeeeee; font-size: 15px; font-weight: 600; }
            QLabel#sectionTitle { color: #bdbdbd; font-size: 12px; font-weight: 600; }
            QFrame#sectionDivider { background: #2b2b2b; border: none; max-height: 1px; }
            QLabel#status { color: #aaaaaa; font-size: 12px; }
            QPushButton { min-height: 30px; padding: 0 8px; border-radius: 7px;
                background: #333333; border: 1px solid #373737; color: #d0d0d0; }
            QPushButton:pressed { background: #242424; border-color: #242424; }
            QPushButton#helpIcon:pressed { background: #242424; border-color: #242424; }
            QFrame#customizationTabs { background: #131313; border: 1px solid #383838; border-radius: 6px; }
            QFrame#customizationTabs QPushButton#tab { border: none; border-radius: 4px;
                background: transparent; color: #999999; padding: 0 4px; min-height: 30px; }
            QFrame#customizationTabs QPushButton#tab:checked { color: #eeeeee; background: #303030; }
            QFrame#customizationTabs QPushButton#tab:pressed { background: #242424; }
            QPushButton#apply { background: #246bce; color: #ffffff; border-color: #347cde; }
            QPushButton#apply:hover { background: #307bdf; border-color: #307bdf; }
            QPushButton#apply:pressed { background: #1855ac; border-color: #1855ac; }
            QPushButton:disabled, QPushButton#apply:disabled {
                background: #303030; color: #777777; border-color: #333333; }
            QLineEdit, QComboBox, QDoubleSpinBox { background: #111111;
                border: 1px solid #2c2c2c; border-radius: 5px;
                min-height: 30px; padding: 0 10px; selection-background-color: #246bce; selection-color: #ffffff; }
            QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover { background: #181818; border-color: #444444; }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #686868; }
            QComboBox { padding-right: 30px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right;
                width: 28px; border: none; background: transparent; }
            QComboBox::down-arrow { image: url(@CHEVRON@); width: 12px; height: 8px; }
            QFrame#fpsControl { background: #111111; border: 1px solid #2c2c2c; border-radius: 5px; }
            QFrame#fpsControl:hover { background: #191919; }
            QFrame#fpsControl QDoubleSpinBox, QFrame#fpsControl QLineEdit {
                border: none; background: transparent; border-radius: 0; padding: 0; min-height: 0; }
            QFrame#fpsControl QPushButton#fpsStep { min-height: 0; padding: 0; font-size: 16px;
                background: transparent; border: none; border-radius: 0; outline: none; }
            QFrame#fpsControl QFrame#fpsSeparator { background: #2c2c2c; border: none; }
            QFrame#comboPopup { border: none; background: #1a1a1a; }
            QComboBox QAbstractItemView { background: #1a1a1a; color: #f5f5f5;
                selection-background-color: #303030; selection-color: #ffffff;
                border: none; outline: none; padding: 3px; }
            QComboBox QAbstractItemView::item { min-height: 30px; padding: 0 7px;
                border: none; border-radius: 3px; }
            QComboBox QAbstractItemView::item:selected { background: #303030; color: #eeeeee; border: none; }
            QComboBox QAbstractItemView::item:hover { background: #292929; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 14px; height: 14px; background: #101010;
                border: 1px solid #484848; border-radius: 3px; }
            QCheckBox::indicator:checked { background: #353535; border-color: #666666; image: url(@CHECK@); }
            QSplitter::handle { background: transparent; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #0f0f0f; width: 8px; }
            QScrollBar::handle:vertical { background: #444444; min-height: 24px; }
        """.replace('@CHEVRON@', str(Path(__file__).parent / 'assets/chevron-down.svg'))
            .replace('@CHECK@', str(Path(__file__).parent / 'assets/check.svg'))
            .replace('@CHEVRON_UP@', str(Path(__file__).parent / 'assets/chevron-up.svg')))
        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(18)
        outer.addWidget(splitter)
        sidebar = FrostedPanel()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(268)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(0)
        scroll = SettingsScroll()
        sidebar_layout.addWidget(scroll, 1)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_content = QWidget()
        settings_content.setObjectName('settingsContent')
        scroll.setWidget(settings_content)
        settings_content.setAutoFillBackground(False)
        panel = QVBoxLayout(settings_content)
        panel.setSizeConstraint(QLayout.SetMinAndMaxSize)
        panel.setContentsMargins(13, 15, 13, 15)
        panel.setSpacing(0)

        def section(parent, title):
            group = QVBoxLayout()
            group.setContentsMargins(0, 0, 0, 0)
            group.setSpacing(12)
            heading = QLabel(title)
            heading.setObjectName('sectionTitle')
            group.addWidget(heading)
            parent.addLayout(group)
            return group

        def divider(parent, spacing=24):
            parent.addSpacing(spacing)
            line = QFrame()
            line.setObjectName('sectionDivider')
            line.setFixedHeight(1)
            parent.addWidget(line)
            parent.addSpacing(spacing)
        title = QLabel('Customization')
        title.setObjectName('panelTitle')
        panel.addWidget(title)
        panel.addSpacing(18)
        tab_container = QFrame()
        tab_container.setObjectName('customizationTabs')
        tabs = QHBoxLayout(tab_container)
        tabs.setContentsMargins(2, 2, 2, 2)
        tabs.setSpacing(0)
        self.tabs = QButtonGroup(self)
        self.simple = QPushButton('Simple')
        self.advanced = QPushButton('Advanced')
        for button in (self.simple, self.advanced):
            button.setObjectName('tab')
            button.setCheckable(True)
            self.tabs.addButton(button)
            tabs.addWidget(button)
        self.simple.setChecked(True)
        panel.addWidget(tab_container)
        panel.addSpacing(24)
        application_group = QVBoxLayout()
        application_group.setSpacing(12)
        application_heading = QLabel('Application')
        application_heading.setObjectName('sectionTitle')
        application_group.addWidget(application_heading)
        self.process = ApplicationComboBox()
        self.process.setAccessibleName('Application with MangoHud')
        self.process.currentIndexChanged.connect(self.selection_changed)
        application_group.addWidget(self.process)
        right_sidebar = FrostedPanel()
        right_sidebar.setObjectName('sidebar')
        right_sidebar.setFixedWidth(268)
        right_layout = QVBoxLayout(right_sidebar)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(0)
        right_scroll = SettingsScroll()
        right_scroll.setWidgetResizable(True)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_content = QWidget()
        right_content.setObjectName('settingsContent')
        right_scroll.setWidget(right_content)
        right_content.setAutoFillBackground(False)
        right_layout.addWidget(right_scroll, 1)
        limits = QVBoxLayout(right_content)
        limits.setContentsMargins(13, 15, 13, 15)
        limits.setSpacing(0)
        limiter_header = QWidget()
        header_layout = QVBoxLayout(limiter_header)
        header_layout.setContentsMargins(13, 15, 13, 0)
        header_layout.setSpacing(0)
        limit_title = QLabel('Frame limiter')
        limit_title.setObjectName('panelTitle')
        header_layout.addWidget(limit_title)
        header_layout.addSpacing(18)
        header_layout.addLayout(application_group)
        divider(header_layout, 16)
        right_layout.insertWidget(0, limiter_header)
        limits.setContentsMargins(13, 0, 13, 15)
        limiter_section = section(limits, 'Limit')
        self.show_hud = QCheckBox('Show overlay')
        self.show_hud.setChecked(True)
        self.fps = NoWheelSpinBox()
        # Qt spin boxes normally take keyboard focus on wheel input, even
        # when wheelEvent ignores the value change. Focus only by click/Tab.
        self.fps.setFocusPolicy(Qt.StrongFocus)
        self.fps.lineEdit().setFocusPolicy(Qt.StrongFocus)
        self.fps.setRange(0, 1000)
        self.fps.setDecimals(0)
        self.fps.setSingleStep(1)
        self.fps.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.fps.setValue(60)
        self.fps.setAlignment(Qt.AlignCenter)
        self.fps.setSuffix(' FPS')
        self.fps.setSpecialValueText('0 · Unlimited')
        self.fps.setAccessibleName('FPS limit')
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.setVerticalSpacing(8)
        fps_control = NumberControl(self.fps)
        self.fps_down = fps_control.down
        self.fps_up = fps_control.up
        form.addRow('FPS limit', fps_control)
        limiter_section.addLayout(form)
        self.preview_settings = FrostedPanel()
        self.preview_settings.setObjectName('sidebar')
        self.preview_settings.setFixedWidth(268)
        settings_layout = QVBoxLayout(self.preview_settings)
        settings_layout.setContentsMargins(18, 18, 18, 18)
        settings_layout.setSpacing(0)
        preview_section = section(settings_layout, 'Preview')
        self.pause_preview = QCheckBox('Pause animation')
        self.restart_preview = QPushButton('Restart preview')
        preview_section.addWidget(self.show_hud)
        self.show_hud.toggled.connect(lambda visible: self.preview.set_overlay(visible))
        preview_section.addWidget(self.pause_preview)
        preview_section.addWidget(self.restart_preview)
        self.pause_preview.toggled.connect(lambda paused: self.preview.set_paused(paused))
        self.restart_preview.clicked.connect(self.restart_scene)
        self.simple_panel = QWidget()
        simple_layout = QVBoxLayout(self.simple_panel)
        simple_layout.setContentsMargins(0, 0, 0, 0)
        simple_layout.setSpacing(0)
        panel.addWidget(self.simple_panel)
        metrics_section = section(simple_layout, 'Metrics')
        self.metric_controls = {}
        def metric_checkbox(group, key, label):
            checkbox = QCheckBox(label)
            checkbox.setChecked(mangohud.metric_values('')[key])
            checkbox.setToolTip(key)
            group.addWidget(checkbox)
            self.metric_controls[key] = checkbox

        for key, label in (('fps', 'FPS'), ('frametime', 'Frame time'),
                           ('frame_timing', 'Frame time graph')):
            if key == 'frametime':
                metrics_section.addSpacing(6)
            metric_checkbox(metrics_section, key, label)
        divider(simple_layout)
        hardware_section = section(simple_layout, 'Hardware')
        for parent_key, child_key, name in (('gpu_stats', 'gpu_temp', 'GPU'),
                                             ('cpu_stats', 'cpu_temp', 'CPU')):
            if parent_key == 'cpu_stats':
                hardware_section.addSpacing(6)
            metric_checkbox(hardware_section, parent_key, f'{name} usage')
            temperature = QCheckBox(f'{name} temperature')
            temperature.setChecked(False)
            temperature.setToolTip(child_key)
            self.metric_controls[child_key] = temperature
            hardware_section.addWidget(DependencyRow(self.metric_controls[parent_key], temperature))
        hardware_section.addSpacing(6)
        metric_checkbox(hardware_section, 'ram', 'RAM usage')
        metric_checkbox(hardware_section, 'vram', 'VRAM usage')
        divider(simple_layout)
        misc_section = section(simple_layout, 'Miscellaneous')
        for key, label in (('gamemode', 'GameMode status'), ('vkbasalt', 'vkBasalt status'),
                           ('engine_version', 'Graphics API / engine'),
                           ('vulkan_driver', 'Vulkan driver'), ('wine', 'Wine / Proton version')):
            if key == 'engine_version':
                misc_section.addSpacing(6)
            metric_checkbox(misc_section, key, label)
        self.metric_controls['gamemode'].setToolTip('Show whether GameMode is active; does not enable GameMode.')
        self.metric_controls['vkbasalt'].setToolTip('Show whether vkBasalt is active; does not enable vkBasalt.')
        divider(simple_layout)
        self.appearance_controls = {}
        self.color_controls = {}
        self.text_controls = {}
        self.font_controls = {}
        for title, color_key, color_default, fields in (
            ('Text', 'text_color', 'FFFFFF', (
                ('font_size', 'Font size', 8, 48, 24, ' px'),
                ('font_scale', 'Font scale', .5, 3, 1, ' ×'),
                ('font_size_text', 'Additional text size', 8, 48, 24, ' px'),
                ('text_outline_thickness', 'Outline thickness', .1, 5, 1.5, ' px'),
                ('alpha', 'Text opacity', 0, 100, 100, ' %'))),
            ('Background', 'background_color', '020202', (
                ('background_alpha', 'Background opacity', 0, 100, 50, ' %'),
                ('round_corners', 'Corner radius', 0, 30, 0, ' px'),
                ('vela_padding', 'Padding', 0, 64, 5, ' px'),
                ('vela_background_blur', 'Background blur', 0, 32, 0, ' px'),
                ('vela_background_noise', 'Noise opacity', 0, 100, 0, ' %'))),
            ('Border', 'vela_border_color', '414141', (
                ('vela_border_width', 'Border width', 0, 8, 0, ' px'),
                ('vela_border_alpha', 'Border opacity', 0, 100, 100, ' %'))),
            ('Shadow', 'vela_shadow_color', '000000', (
                ('vela_shadow_alpha', 'Shadow opacity', 0, 100, 0, ' %'),
                ('vela_shadow_blur', 'Softness', 0, 40, 16, ' px'),
                ('vela_shadow_offset_x', 'Horizontal offset', -40, 40, 0, ' px'),
                ('vela_shadow_offset_y', 'Vertical offset', -40, 40, 4, ' px'))),
        ):
            group = section(simple_layout, title)
            if title == 'Text':
                for key, label in (('font_file', 'Font'), ('font_file_text', 'Additional text font')):
                    group.addWidget(QLabel(label))
                    row = QHBoxLayout()
                    row.setSpacing(6)
                    choose = QPushButton()
                    choose.setMinimumWidth(0)
                    choose.setAccessibleName(label)
                    self.font_controls[key] = choose
                    self.set_customization_font(key, '')
                    choose.clicked.connect(lambda checked=False, key=key: self.choose_customization_font(key))
                    if key == 'font_file_text':
                        choose.setContextMenuPolicy(Qt.CustomContextMenu)
                        choose.customContextMenuRequested.connect(lambda pos, key=key: self.show_font_file_menu(key, pos))
                    reset = QPushButton()
                    reset.setIcon(QIcon(str(Path(__file__).parent / 'assets/reset.svg')))
                    reset.setIconSize(QSize(16, 16))
                    reset.setFixedWidth(32)
                    reset.setAccessibleName(f'Reset {label.lower()}')
                    reset.setToolTip('Restore default font' if key == 'font_file' else 'Use the main font')
                    reset.clicked.connect(lambda checked=False, key=key: self.reset_customization_font(key))
                    row.addWidget(choose, 1)
                    presets = QPushButton()
                    presets.setIcon(QIcon(str(Path(__file__).parent / 'assets/fonts.svg')))
                    presets.setIconSize(QSize(18, 18))
                    presets.setFixedWidth(32)
                    presets.setAccessibleName(f'Font presets for {label.lower()}')
                    presets.setToolTip('Browse downloadable fonts and weights')
                    presets.clicked.connect(lambda checked=False, key=key: self.open_font_catalog(key))
                    row.addWidget(presets)
                    row.addWidget(reset)
                    group.addLayout(row)
            group.addWidget(QLabel('Color'))
            button = QPushButton()
            button.setAccessibleName(f'{title} color')
            button.setToolTip(color_key)
            self.color_controls[color_key] = button
            self.set_customization_color(color_key, color_default)
            button.clicked.connect(lambda checked=False, key=color_key: self.choose_customization_color(key))
            group.addWidget(button)
            for key, label, minimum, maximum, default, suffix in fields:
                group.addSpacing(6)
                field = NoWheelSpinBox()
                field.setDecimals(1 if key in ('font_scale', 'text_outline_thickness', 'vela_background_noise', 'vela_border_width') else 0)
                field.setSingleStep(.1 if key in ('font_scale', 'text_outline_thickness', 'vela_border_width') else 1)
                field.setRange(minimum, maximum)
                field.setValue(default)
                field.setSuffix(suffix)
                if key in ('vela_border_width', 'vela_shadow_alpha', 'vela_background_blur'):
                    field.setSpecialValueText('Off')
                field.setButtonSymbols(QAbstractSpinBox.NoButtons)
                field.setFocusPolicy(Qt.StrongFocus)
                field.setAccessibleName(label)
                field.setToolTip(key)
                group.addWidget(QLabel(label))
                group.addWidget(NumberControl(field))
                self.appearance_controls[key] = field
            if title == 'Text':
                self.appearance_controls['font_size_text'].setToolTip('Size of additional text such as media player metadata (font_size_text).')
                for key, label, default in (('no_small_font', 'Full-size units', False),
                                             ('text_outline', 'Text outline', True)):
                    checkbox = QCheckBox(label)
                    checkbox.setChecked(default)
                    checkbox.setToolTip(key)
                    self.text_controls[key] = checkbox
                    group.addWidget(checkbox)
                outline_color = QPushButton()
                outline_color.setAccessibleName('Text outline color')
                self.color_controls['text_outline_color'] = outline_color
                self.set_customization_color('text_outline_color', '000000')
                outline_color.clicked.connect(lambda: self.choose_customization_color('text_outline_color'))
                group.addWidget(QLabel('Outline color'))
                group.addWidget(outline_color)
                self.text_controls['text_outline'].toggled.connect(outline_color.setEnabled)
                self.text_controls['text_outline'].toggled.connect(self.appearance_controls['text_outline_thickness'].setEnabled)
                divider(simple_layout)
            elif title == 'Background':
                self.appearance_controls['vela_background_blur'].setToolTip(
                    'Experimental GPU blur of the game behind the HUD; 0 disables it. Requires desktop OpenGL 3+ or a compatible SDR Vulkan swapchain. Lower background opacity to see it.')
                self.appearance_controls['vela_padding'].setToolTip(
                    'Equal inner spacing on all sides. The panel grows to preserve content width; the HUD anchor stays fixed. Thick borders keep a safe minimum inset. Requires Vela MangoHud.')
                self.appearance_controls['vela_background_noise'].setToolTip(
                    'Opacity of a subtle, low-contrast grain layer. 0% is invisible; 100% shows the full texture. Requires Vela MangoHud.')
                if not textured_runtime_available():
                    self.appearance_controls['vela_background_noise'].editing_container.setEnabled(False)
                    self.appearance_controls['vela_padding'].editing_container.setEnabled(False)
                    self.appearance_controls['vela_background_blur'].editing_container.setEnabled(False)
                hint = QLabel('Experimental · Vela MangoHud required for games.')
                hint.setWordWrap(True)
                hint.setStyleSheet('color: #999999; font-size: 11px;')
                group.addWidget(hint)
                divider(simple_layout)
            elif title == 'Border':
                button.setToolTip('Border color; set Border width above 0 px to enable. Requires Vela MangoHud.')
                self.appearance_controls['vela_border_width'].setToolTip(
                    'HUD border thickness; 0 px disables the border. Uses Background corner radius. Requires Vela MangoHud.')
                self.appearance_controls['vela_border_alpha'].setToolTip(
                    'Border opacity, independent of the background opacity.')
                if not textured_runtime_available():
                    button.setEnabled(False)
                    for key in ('vela_border_width', 'vela_border_alpha'):
                        self.appearance_controls[key].editing_container.setEnabled(False)
                divider(simple_layout)
            else:
                button.setToolTip('Color of the soft shadow behind the HUD. Requires Vela MangoHud.')
                self.appearance_controls['vela_shadow_alpha'].setToolTip('Shadow opacity; 0% disables the shadow.')
                self.appearance_controls['vela_shadow_blur'].setToolTip('Shadow softness; 0 px gives a hard edge.')
                self.appearance_controls['vela_shadow_offset_x'].setToolTip('Negative moves left, positive moves right.')
                self.appearance_controls['vela_shadow_offset_y'].setToolTip('Negative moves up, positive moves down.')
                if not textured_runtime_available():
                    button.setEnabled(False)
                    for key in ('vela_shadow_alpha', 'vela_shadow_blur', 'vela_shadow_offset_x', 'vela_shadow_offset_y'):
                        self.appearance_controls[key].editing_container.setEnabled(False)

        self.advanced_panel = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(0)
        self.pacing_panel = QWidget()
        pacing_layout = QVBoxLayout(self.pacing_panel)
        pacing_layout.setContentsMargins(0, 0, 0, 0)
        pacing_layout.setSpacing(0)
        divider(pacing_layout, 8)
        pacing_section = section(pacing_layout, 'Pacing')
        limits.addWidget(self.pacing_panel)
        self.method = NoWheelComboBox()
        self.method.addItem('Early · smooth pacing', 'early')
        self.method.addItem('Late · low latency', 'late')
        pacing_section.addWidget(QLabel('Limiter mode'))
        pacing_section.addWidget(self.method)
        self.experimental_panel = FrostedPanel()
        self.experimental_panel.setObjectName('sidebar')
        self.experimental_panel.setFixedWidth(268)
        experimental_layout = QVBoxLayout(self.experimental_panel)
        experimental_layout.setContentsMargins(18, 18, 18, 18)
        experimental_layout.setSpacing(0)
        experimental_title = QLabel('Experimental functions')
        experimental_title.setObjectName('panelTitle')
        experimental_layout.addWidget(experimental_title)
        experimental_layout.addSpacing(18)
        compatibility_section = section(experimental_layout, 'Compatibility')
        fix_row = QHBoxLayout()
        fix_row.setSpacing(10)
        self.fix_lsfg = QPushButton('Fix LSFG')
        self.fix_lsfg.clicked.connect(self.configure_lsfg)
        self.remove_lsfg = QPushButton()
        self.remove_lsfg.setIcon(QIcon(str(Path(__file__).parent / 'assets/trash.svg')))
        self.remove_lsfg.setIconSize(QSize(18, 18))
        self.remove_lsfg.setObjectName('helpIcon')
        self.remove_lsfg.setFixedSize(28, 28)
        self.remove_lsfg.setAccessibleName('Remove LSFG fix')
        self.remove_lsfg.setToolTip('Remove the LSFG fix configuration and Vela layer manifests. Restart the game afterwards.')
        self.remove_lsfg.clicked.connect(self.remove_lsfg_fix)
        self.remove_lsfg.hide()
        self.lsfg_help = QPushButton()
        self.lsfg_help.setIcon(QIcon(str(Path(__file__).parent / 'assets/help.svg')))
        self.lsfg_help.setIconSize(QSize(18, 18))
        self.lsfg_help.setObjectName('helpIcon')
        self.lsfg_help.setFixedSize(28, 28)
        self.lsfg_help.setFocusPolicy(Qt.NoFocus)
        self.lsfg_help.setAccessibleName('About Fix LSFG')
        explanation = (
            'Creates a Vulkan Loader configuration that places MangoHud before lsfg-vk.\n'
            'The FPS limit applies to base frames before frame generation.\n'
            'MangoHud then counts base FPS, not the generated frames.\n'
            'Restart the game for the new layer order to take effect.\n'
            'This does not enable LSFG or change its multiplier.'
        )
        self.lsfg_help.setToolTip('Explain how Fix LSFG works')
        self.lsfg_help.clicked.connect(self.show_lsfg_help)
        self.fix_lsfg.setToolTip(explanation)
        fix_row.addWidget(self.fix_lsfg, 1)
        fix_row.addWidget(self.remove_lsfg)
        fix_row.addWidget(self.lsfg_help)
        compatibility_section.addLayout(fix_row)
        divider(experimental_layout, 16)
        reshade_section = section(experimental_layout, 'ReShade')
        reshade_placeholder = QLabel('No options configured yet.')
        reshade_placeholder.setWordWrap(True)
        reshade_placeholder.setStyleSheet('color: #888888; font-size: 12px;')
        reshade_section.addWidget(reshade_placeholder)
        experimental_layout.addStretch(1)

        self.preferences = QSettings('Vela', 'Vela')
        try:
            saved_width = int(self.preferences.value('window_width', 1400))
        except (TypeError, ValueError, OverflowError):
            saved_width = 1400
        try:
            saved_height = int(self.preferences.value('window_height', 780))
        except (TypeError, ValueError, OverflowError):
            saved_height = 780
        self.resize(max(self.minimumWidth(), min(saved_width, self.maximumWidth())),
                    max(self.minimumHeight(), min(saved_height, self.maximumHeight())))
        self.config_path = PathEdit(str(self.preferences.value(
            'global_config', str(mangohud.default_config()))))
        self.config_path.setAccessibleName('Global MangoHud configuration')
        self.config_path.setToolTip('Preview inherits this file; FPS, limiter mode and overlay controls override it only in the preview.')
        config_row = QWidget()
        config_layout = QHBoxLayout(config_row)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(6)
        config_layout.addWidget(self.config_path, 1)
        self.browse_config = QPushButton('…')
        self.browse_config.setFixedWidth(32)
        self.browse_config.setAccessibleName('Choose MangoHud configuration')
        config_layout.addWidget(self.browse_config)
        config_section = section(advanced_layout, 'Configuration')
        config_section.addWidget(QLabel('Global MangoHud file'))
        config_section.addWidget(config_row)
        self.open_config_directory = QPushButton('Open directory')
        self.open_config_directory.setIcon(QIcon.fromTheme('folder-open',
            self.style().standardIcon(QStyle.SP_DirOpenIcon)))
        self.open_config_directory.clicked.connect(self.open_configuration_directory)
        config_section.addWidget(self.open_config_directory)
        self.config_contents = QPlainTextEdit()
        self.config_contents.setReadOnly(True)
        self.config_contents.setAccessibleName('Global configuration contents')
        self.config_contents.setMinimumHeight(180)
        self.config_contents.setMaximumHeight(260)
        self.config_contents.setStyleSheet('QPlainTextEdit { background: #111111; color: #aaaaaa; border: 1px solid #2c2c2c; border-radius: 5px; padding: 8px; font-family: monospace; font-size: 11px; }')
        config_section.addSpacing(6)
        config_section.addWidget(QLabel('File contents'))
        config_section.addWidget(self.config_contents)
        self.advanced.toggled.connect(lambda active: self.update_config_contents() if active else None)
        self.config_path.editingFinished.connect(self.change_global_config)
        self.browse_config.clicked.connect(self.choose_global_config)
        panel.addWidget(self.advanced_panel)
        self.advanced_panel.hide()
        self.page_motion = PageMotion(self, (simple_layout, advanced_layout))
        self.advanced.toggled.connect(self.page_motion.start)
        self.advanced.toggled.connect(self.advanced_panel.setVisible)
        self.advanced.toggled.connect(lambda active: self.simple_panel.setVisible(not active))
        self.advanced.toggled.connect(lambda _: QTimer.singleShot(0, lambda: (settings_content.adjustSize(), scroll.verticalScrollBar().setValue(0), scroll.update_fade())))
        self.advanced.toggled.connect(lambda _: self.refresh() if hasattr(self, "sessions") else None)
        # Future MangoHud controls can be added to this scrollable panel.
        panel.addSpacing(24)
        panel.addStretch()
        self.save_config = QPushButton('Save configuration')
        self.save_config.setObjectName('apply')
        self.save_glow = ButtonGlow(self.save_config)
        self.save_config.setToolTip('Save appearance and metrics to the selected game’s existing profile, or to the global configuration if no game profile exists.')
        self.save_config.clicked.connect(self.configuration_action)
        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(12)
        self.status = Notification()
        divider(limits, 16)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.apply = QPushButton('Apply')
        self.apply.setObjectName('apply')
        self.apply.setDefault(True)
        self.disable = QPushButton('Disable limit')
        self.disable.setObjectName('secondary')
        self.apply.setMinimumWidth(0)
        self.disable.setMinimumWidth(0)
        buttons.addWidget(self.apply, 1)
        buttons.addWidget(self.disable, 1)
        footer_layout.addLayout(buttons)
        splitter.addWidget(sidebar)
        self.preview = Preview()
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.preview_source = ElidedLabel('Global configuration')
        self.preview_source.setStyleSheet('color: #999999; font-size: 12px; padding: 0 16px;')
        self.preview_source.setFixedHeight(28)
        center_layout.addWidget(self.preview_source)
        center_layout.addWidget(self.preview, 1)
        self.preview_toolbar = QWidget()
        self.preview_toolbar.setFixedHeight(88)
        toolbar_layout = QHBoxLayout(self.preview_toolbar)
        toolbar_layout.setContentsMargins(16, 16, 16, 32)
        toolbar_layout.setSpacing(8)
        self.save_config.setMinimumWidth(240)
        self.save_config.setMaximumWidth(360)
        self.save_config.setFixedHeight(40)
        self.preview_options = QPushButton()
        self.preview_options.setIcon(QIcon(str(Path(__file__).parent / 'assets/camera.svg')))
        self.preview_options.setIconSize(QSize(20, 20))
        self.preview_options.setFixedSize(44, 40)
        self.preview_options.setCheckable(True)
        self.preview_options.setAccessibleName('Preview options')
        self.preview_options.setToolTip('Preview options')
        self.preview_options.clicked.connect(self.toggle_preview_options)
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(str(Path(__file__).parent / 'assets/settings.svg')))
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setFixedSize(44, 40)
        self.settings_button.setAccessibleName('Settings')
        self.settings_button.setToolTip('Settings — not configured yet')
        self.settings_button.setEnabled(False)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.save_config, 3)
        toolbar_layout.addWidget(self.preview_options)
        toolbar_layout.addWidget(self.settings_button)
        toolbar_layout.addStretch(1)
        self.preview_menu = QMenu(self)
        self.preview_menu.setStyleSheet('QMenu { background: #1b1b1d; border: 1px solid #414141; border-radius: 8px; padding: 4px; }')
        preview_action = QWidgetAction(self.preview_menu)
        preview_action.setDefaultWidget(self.preview_settings)
        self.preview_menu.addAction(preview_action)
        self.preview_menu.aboutToHide.connect(lambda: self.preview_options.setChecked(False))
        # The native transient notification stacks above the live GL window.
        center_layout.addWidget(self.preview_toolbar)
        self.status.bottom_inset = 104
        self.status.presenting.connect(self.preview.prepare_notification)
        self.status.opacity_changed.connect(self.preview.set_notification_opacity)
        self.status.dismissed.connect(self.preview.finish_notification)
        self.status.choice_closed.connect(self.finish_save_choice)
        limits.addWidget(footer)
        right_sidebar.setFixedHeight(
            limiter_header.sizeHint().height() + right_content.sizeHint().height()
            + right_scroll.frameWidth() * 2 + 60)
        splitter.addWidget(center)
        self.status.attach_to(center)
        right_column = QWidget()
        right_column.setFixedWidth(268)
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(12)
        right_column_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        right_column_layout.addWidget(right_sidebar)
        right_column_layout.addWidget(self.experimental_panel, 1)
        settings_layout.addStretch()
        right_column_scroll = SettingsScroll()
        right_column_scroll.setFixedWidth(268)
        right_column_scroll.setWidgetResizable(True)
        right_column_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_column_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_column_scroll.setWidget(right_column)
        right_column.setAutoFillBackground(False)
        splitter.addWidget(right_column_scroll)
        splitter.setSizes([268, 800, 268])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setChildrenCollapsible(False)
        # Keep the pointer stable while scrolling over editable controls.
        for control in self.findChildren(QWidget):
            control.setCursor(Qt.ArrowCursor)
            if control.focusPolicy() == Qt.WheelFocus:
                control.setFocusPolicy(Qt.StrongFocus)
        self.button_motion = [ButtonMotion(button) for button in self.findChildren(QPushButton) + self.findChildren(QCheckBox)]
        self.configuration_controls = (settings_content, right_content,
                                       self.preview_settings, self.preview.retry, self.preview_options,
                                       self.experimental_panel)
        self.configuration_fades = []
        for widget in self.configuration_controls:
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(1.)
            widget.setGraphicsEffect(effect)
            self.configuration_fades.append(effect)
        self.sessions = []
        self.pending = None
        self.message_until = 0
        self.apply.clicked.connect(lambda: self.write(self.fps.value()))
        self.loading_customization = False
        for field in self.appearance_controls.values():
            field.valueChanged.connect(self.apply_customization)
        for checkbox in self.metric_controls.values():
            checkbox.toggled.connect(self.apply_customization)
        for checkbox in self.text_controls.values():
            checkbox.toggled.connect(self.apply_customization)
        self.disable.clicked.connect(self.disable_limit)
        try:
            self.load_global_preview()
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot load global configuration: {error}')
        self.selection_changed()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def restart_scene(self):
        self.preview.stop()
        self.preview.start()

    def toggle_preview_options(self):
        if self.preview_menu.isVisible():
            self.preview_menu.hide()
            return
        self.preview_menu.ensurePolished()
        size = self.preview_menu.sizeHint()
        position = self.preview_options.mapToGlobal(QPoint(
            (self.preview_options.width() - size.width()) // 2, -size.height() - 8))
        available = self.screen().availableGeometry()
        position.setX(max(available.left(), min(position.x(), available.right() - size.width() + 1)))
        position.setY(max(available.top(), position.y()))
        self.preview_options.setChecked(True)
        self.preview_menu.popup(position)

    def paintEvent(self, event):
        # Cache the static background; hovering controls never rebuilds the grid.
        scale = self.devicePixelRatioF()
        key = (self.width(), self.height(), scale)
        if getattr(self, '_background_key', None) != key:
            canvas = QPixmap(round(self.width() * scale), round(self.height() * scale))
            canvas.setDevicePixelRatio(scale)
            canvas.fill(QColor('#090909'))
            center = QPointF(self.width() * .5, self.height() * .5)
            radius = max(self.width() * .75, self.height() * .95)
            glow = QRadialGradient(center, radius)
            glow.setColorAt(0, QColor('#121212'))
            glow.setColorAt(1, QColor('#090909'))
            painter = QPainter(canvas)
            painter.fillRect(self.rect(), glow)
            grid = QPixmap(canvas.size())
            grid.setDevicePixelRatio(scale)
            grid.fill(Qt.transparent)
            lines = QPainter(grid)
            lines.setPen(QPen(QColor(255, 255, 255, 16), 1))
            for x in range(0, self.width(), 36):
                lines.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), 36):
                lines.drawLine(0, y, self.width(), y)
            fade = QRadialGradient(center, radius)
            fade.setColorAt(0, QColor(0, 0, 0, 255))
            fade.setColorAt(.45, QColor(0, 0, 0, 130))
            fade.setColorAt(.8, QColor(0, 0, 0, 20))
            fade.setColorAt(1, QColor(0, 0, 0, 0))
            lines.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            lines.fillRect(self.rect(), fade)
            lines.end()
            painter.drawPixmap(0, 0, grid)
            painter.end()
            self._background = canvas
            self._background_key = key
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background)

    def update_config_contents(self):
        path = Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser()
        try:
            content = path.read_text()
            self.config_contents.setPlainText(content if content.strip() else '# Empty configuration')
        except (OSError, UnicodeError) as error:
            self.config_contents.setPlainText(f'# Cannot read configuration: {error}')

    def change_global_config(self):
        value = self.config_path.text().strip() or str(mangohud.default_config())
        self.config_path.setText(value)
        self.preferences.setValue('global_config', value)
        self.load_global_preview()
        if hasattr(self, 'sessions'):
            self.selection_changed()
        self.update_config_contents()

    def configuration_target(self):
        session = self.selected()
        if session is not None and session.pid != self.preview.pid and session.profile.is_file():
            return session.profile.absolute()
        return Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser().absolute()

    def update_configuration_button(self):
        path = self.configuration_target()
        different = path != self.preview.global_config
        changed = self.configuration_has_changes(path) if not different else False
        self.save_config.setText(('Load game config' if self.selected() and path == self.selected().profile.absolute()
                                  else 'Load global config') if different else
                                 ('Save configuration' if changed else 'No changes to save'))
        self.save_config.setEnabled(different or changed)
        self.save_config.setStyleSheet(
            'QPushButton#apply { background: #a83232; border-color: #c64545; }'
            'QPushButton#apply:hover { background: #bd3b3b; }'
            'QPushButton#apply:pressed { background: #862828; }' if different else
            ('QPushButton#apply:disabled { background: #303030; color: #888888; border-color: #414141; }'
             if not changed else ''))
        self.save_config.setToolTip(
            f'{"A different configuration is available. Load it into the preview" if different else "Save appearance and metrics" if changed else "No changes to save — settings match this file"}:\n{path}')
        choosing = self.status.actions is not None
        self.save_config.setEnabled((different or changed) and not choosing)
        self.save_glow.set_active(changed and not different and not choosing)
        for widget, effect in zip(self.configuration_controls, self.configuration_fades):
            widget.setEnabled(not different and not choosing)
            effect.setOpacity(.5 if different else .7 if choosing else 1.)
        session = self.selected()
        available = session is not None and not session.reason and not different and not choosing
        self.apply.setEnabled(available)
        self.disable.setEnabled(available)

    def configuration_has_changes(self, path):
        try:
            if not path.exists():
                return True
            content = path.read_text()
            if any(button.property('font_path') != mangohud.font_values(content)[key]
                   for key, button in self.font_controls.items()):
                return True
            appearance = mangohud.appearance_values(content)
            for key, field in self.appearance_controls.items():
                scale = 100 if key in ('background_alpha', 'alpha', 'vela_background_noise', 'vela_border_alpha', 'vela_shadow_alpha') else 1
                if field.value() != round(appearance[key] * scale, field.decimals()):
                    return True
            if any(button.property('color') != mangohud.color_values(content)[key]
                   for key, button in self.color_controls.items()):
                return True
            if any(field.isChecked() != mangohud.text_values(content)[key]
                   for key, field in self.text_controls.items()):
                return True
            return any(field.isChecked() != mangohud.metric_values(content)[key]
                       for key, field in self.metric_controls.items())
        except (OSError, ValueError):
            return True

    def configuration_action(self):
        try:
            path = self.configuration_target()
            if path != self.preview.global_config:
                # Read first so an unreadable profile leaves the preview intact.
                path.read_text()
                self.selection_changed()
                self.load_preview_configuration(path)
                self.status.show_message('Configuration loaded', path)
                self.message_until = time.monotonic() + 6
            else:
                self.save_configuration()
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot load configuration: {error}')
            self.message_until = time.monotonic() + 6
        self.update_configuration_button()

    def save_configuration(self, destination=None, expected_identity=None):
        try:
            global_path = Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser().absolute()
            session = self.selected()
            if expected_identity is not None and (session is None or session.identity != expected_identity):
                self.status.setText('Application changed. Choose where to save again.')
                return
            path = global_path
            if session is not None and session.pid != self.preview.pid:
                if destination is None:
                    self.choose_save_destination(session, global_path)
                    return
                if destination == 'profile':
                    if session.profile.is_symlink():
                        raise mangohud.ControlError('The MangoHud profile is a symlink; the shared file will not be changed.')
                    path = session.profile.absolute()
            appearance = self.customization_values()
            appearance.update({key: int(field.isChecked()) for key, field in self.metric_controls.items()})
            mangohud.save_appearance(path, appearance, template=global_path)
            if path == global_path:
                self.load_global_preview()
                self.update_config_contents()
            else:
                self.load_preview_configuration(path)
            self.status.show_message('Game profile saved' if path != global_path else 'Global configuration saved', path)
            self.status.setToolTip(str(path))
        except (mangohud.ControlError, OSError, ValueError, UnicodeError) as error:
            self.status.setText(f'Cannot save configuration: {error}')
        self.message_until = time.monotonic() + 10
        self.update_configuration_button()

    def choose_save_destination(self, session, global_path):
        identity = session.identity
        self.status.show_choice(
            session.name, global_path, session.profile,
            lambda: self.save_configuration('global', identity),
            lambda: self.save_configuration('profile', identity),
            self.status.dismiss,
        )
        self.message_until = 0
        self.update_configuration_button()

    def finish_save_choice(self):
        self.message_until = 0
        if hasattr(self, 'sessions'):
            self.update_configuration_button()

    def show_lsfg_help(self):
        self.status.show_message(
            'How Fix LSFG works',
            'Places MangoHud before LSFG so the limiter and FPS counter use base frames.\n'
            'Click Fix LSFG to enable it, then restart the game.\n'
            'Use the trash icon to remove the fix, then restart the game again.\n'
            'It does not enable frame generation or change the LSFG multiplier.',
            duration=15000,
        )
        self.message_until = time.monotonic() + 15

    def configure_lsfg(self):
        try:
            path = layer_order.configure()
            self.status.setText('LSFG order configured. Restart the game.')
            self.status.setToolTip(str(path))
        except (OSError, ValueError, KeyError) as error:
            self.status.setText(str(error))
        self.update_lsfg_status()
        self.message_until = time.monotonic() + 10

    def remove_lsfg_fix(self):
        try:
            layer_order.remove()
            self.status.setText('LSFG fix removed. Restart the game.')
        except (OSError, ValueError) as error:
            self.status.setText(f'Cannot remove LSFG fix: {error}')
        self.update_lsfg_status()
        self.message_until = time.monotonic() + 10

    def update_lsfg_status(self):
        state, description = layer_order.configuration_status()
        self.fix_lsfg.setText({
            'missing': 'Fix LSFG',
            'enabled': 'LSFG fix enabled',
            'invalid': 'Repair LSFG fix',
            'foreign': 'LSFG config in use',
        }[state])
        self.fix_lsfg.setEnabled(state in ('missing', 'invalid'))
        self.fix_lsfg.setToolTip(description)
        self.remove_lsfg.setVisible(state == 'enabled')

    def open_configuration_directory(self):
        path = Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser().absolute().parent
        if not path.is_dir():
            self.status.setText('Configuration directory does not exist.')
            self.message_until = time.monotonic() + 6
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.status.setText('Could not open the configuration directory.')
            self.message_until = time.monotonic() + 6

    def choose_global_config(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Global MangoHud configuration',
            str(Path(self.config_path.text()).expanduser()), 'Configuration files (*.conf);;All files (*)')
        if path:
            self.config_path.setText(path)
            self.change_global_config()

    def update_preview(self, *_):
        self.preview.update_options(self.fps.value(), self.method.currentData(), self.show_hud.isChecked())

    def load_global_preview(self):
        path = Path(self.config_path.text()).expanduser().absolute()
        self.load_preview_configuration(path)

    def load_preview_configuration(self, path):
        content = path.read_bytes() if path.exists() else b''
        _, _, visible = mangohud.values_from_content(content.decode('utf-8'))
        self.preview.set_global_config(path, content=content)
        self.show_hud.blockSignals(True)
        self.show_hud.setChecked(visible)
        self.show_hud.blockSignals(False)
        self.update_preview_source(path)

    def update_preview_source(self, path):
        global_path = Path(self.config_path.text()).expanduser().absolute()
        name = 'Global configuration' if path == global_path else path.name
        self.preview_source.full_text = f'Preview · {name}'
        self.preview_source.setToolTip(str(path))
        self.preview_source.setText(self.preview_source.fontMetrics().elidedText(
            self.preview_source.full_text, Qt.ElideMiddle, self.preview_source.width()))

    def closeEvent(self, event):
        size = self.normalGeometry().size() if self.isMaximized() or self.isFullScreen() else self.size()
        self.preferences.setValue('window_width', max(self.minimumWidth(), size.width()))
        self.preferences.setValue('window_height', max(self.minimumHeight(), size.height()))
        self.preferences.sync()
        self.timer.stop()
        self.status.motion.stop()
        self.status.expiry.stop()
        self.status.hide()
        self.preview.shutdown()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.status.actions is not None:
            self.status.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def selected(self):
        identity = self.process.currentData()
        return next((session for session in self.sessions if session.identity == identity), None)

    def selected_config(self):
        global_path = Path(self.config_path.text()).expanduser().absolute()
        session = self.selected()
        if session is None or session.pid == self.preview.pid:
            return global_path
        return mangohud.profile_config(session, global_path) or global_path

    def selection_changed(self):
        if not hasattr(self, 'sessions'):
            return
        if self.status.actions is not None:
            self.status.dismiss()
        self.pending = None
        self.message_until = 0
        self.loading_customization = True
        try:
            path = self.selected_config()
            content = path.read_text() if path.exists() else ''
            fps, method, visible = mangohud.config_values(path)
            for key, value in mangohud.font_values(content).items():
                self.set_customization_font(key, value)
            for key, enabled in mangohud.metric_values(content).items():
                self.metric_controls[key].setChecked(enabled)
            for key, color in mangohud.color_values(content).items():
                self.set_customization_color(key, color)
            for key, enabled in mangohud.text_values(content).items():
                self.text_controls[key].setChecked(enabled)
            appearance = mangohud.appearance_values(content)
            for key, field in self.appearance_controls.items():
                value = appearance[key] * (100 if key in ('background_alpha', 'alpha', 'vela_background_noise', 'vela_border_alpha', 'vela_shadow_alpha') else 1)
                decimals = min(3, len(str(value).partition('.')[2].rstrip('0')))
                field.setDecimals(max(field.decimals(), decimals))
                field.setRange(min(field.minimum(), value), max(field.maximum(), value))
                field.setValue(value)
            self.fps.setValue(fps if 0 <= fps <= 1000 else 0)
            self.method.setCurrentIndex(1 if method == 'late' else 0)
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot load application configuration: {error}')
            self.message_until = time.monotonic() + 6
        finally:
            self.loading_customization = False
            self.update_configuration_button()

    def set_customization_color(self, key, value):
        button = self.color_controls[key]
        button.setProperty('color', value)
        button.setText(f'#{value}')
        icon = QPixmap(18, 18)
        icon.fill(QColor(f'#{value}'))
        button.setIcon(QIcon(icon))

    def choose_customization_color(self, key):
        button = self.color_controls[key]
        color = QColorDialog.getColor(QColor('#' + button.property('color')), self, button.accessibleName())
        if color.isValid():
            self.set_customization_color(key, color.name()[1:].upper())
            self.apply_customization()

    def customization_values(self):
        values = {key: field.value() / (100 if key in ('background_alpha', 'alpha', 'vela_background_noise', 'vela_border_alpha', 'vela_shadow_alpha') else 1)
                  for key, field in self.appearance_controls.items()}
        values.update({key: button.property('color') for key, button in self.color_controls.items()})
        values.update({key: int(field.isChecked()) for key, field in self.text_controls.items()})
        values.update({key: button.property('font_path') for key, button in self.font_controls.items()})
        return values

    def set_customization_font(self, key, path):
        button = self.font_controls[key]
        button.setProperty('font_path', path)
        label = Path(path).name if path else ('Default font' if key == 'font_file' else 'Same as main font')
        button.setText(button.fontMetrics().elidedText(label, Qt.ElideMiddle, 145))
        hint = ('Click to use the main font. Right-click to choose a TTF/OTF file.'
                if key == 'font_file_text' else 'Choose a TTF/OTF file.')
        button.setToolTip((path or label) + '\n' + hint + ' Use Restart preview if the font does not refresh.')

    def open_font_catalog(self, key):
        from .font_catalog import FontCatalog
        if not hasattr(self, 'font_catalog'):
            self.font_catalog = FontCatalog(self, self.use_catalog_font)
        self.font_catalog.open(key)

    def use_catalog_font(self, key, path):
        self.set_customization_font(key, path)
        self.apply_customization()

    def choose_customization_font(self, key):
        if key == 'font_file_text':
            main = self.font_controls['font_file'].property('font_path')
            if main:
                self.set_customization_font(key, main)
                self.apply_customization()
                return
        self.browse_customization_font(key)

    def show_font_file_menu(self, key, position):
        menu = QMenu(self)
        menu.addAction('Choose font file…', lambda: self.browse_customization_font(key))
        menu.exec(self.font_controls[key].mapToGlobal(position))

    def browse_customization_font(self, key):
        current = self.font_controls[key].property('font_path')
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose font',
            current or str(Path.home() / '.local/share/fonts'), 'Fonts (*.ttf *.otf *.TTF *.OTF)')
        if not filename:
            return
        path = Path(filename).expanduser().absolute()
        try:
            if path.suffix.lower() not in ('.ttf', '.otf') or not path.is_file():
                raise ValueError('Choose an existing TTF or OTF font file.')
            mangohud.managed_content('', 0, 'early', True, {key: str(path)})
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id < 0:
                raise ValueError('This file could not be loaded as a font.')
            QFontDatabase.removeApplicationFont(font_id)
            self.set_customization_font(key, str(path))
            self.apply_customization()
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot use font: {error}')
            self.message_until = time.monotonic() + 6

    def reset_customization_font(self, key):
        self.set_customization_font(key, '')
        self.apply_customization()

    def apply_customization(self, *_):
        if self.loading_customization:
            return
        try:
            options = self.customization_values()
            options.update({key: int(field.isChecked()) for key, field in self.metric_controls.items()})
            # Only the private preview changes until Save configuration is used.
            self.preview.appearance = options
            self.preview.update_options(*self.preview.options)
        except (mangohud.ControlError, OSError, ValueError) as error:
            self.status.setText(str(error))
            self.message_until = time.monotonic() + 6
        finally:
            self.update_configuration_button()

    def disable_limit(self):
        self.fps.setValue(0)
        self.write(0)

    def write(self, fps, include_hud=False):
        session = self.selected()
        if session is None:
            return
        try:
            _, _, saved_hud = mangohud.config_values(self.selected_config())
            appearance = None
            if include_hud:
                appearance = self.customization_values()
                appearance.update({key: int(field.isChecked()) for key, field in self.metric_controls.items()})
            target = mangohud.apply(session, fps, self.method.currentData(), saved_hud, appearance, global_config=self.config_path.text())
            self.preview.update_options(fps, self.method.currentData(), self.show_hud.isChecked())
            self.pending = (session.identity, target, fps, self.method.currentData(), time.monotonic())
            self.status.setText('Applying settings…')
            self.message_until = 0
        except (mangohud.ControlError, OSError, ValueError) as error:
            self.status.setText(str(error))
            self.message_until = time.monotonic() + 6

    def refresh(self):
        self.update_lsfg_status()
        identity = self.process.currentData()
        self.sessions = mangohud.discover()
        entries = [(f'{"3D scene (preview)" if session.pid == self.preview.pid else session.name} · PID {session.pid}',
                    session.identity) for session in self.sessions]
        old = [(self.process.itemText(i), self.process.itemData(i))
               for i in range(self.process.count())]
        if old != entries:
            self.process.blockSignals(True)
            self.process.clear()
            for label, identity_key in entries:
                self.process.addItem(label, identity_key)
            index = next((i for i, session in enumerate(self.sessions) if session.identity == identity), 0)
            self.process.setCurrentIndex(index)
            self.process.blockSignals(False)
            if self.process.currentData() != identity:
                self.selection_changed()
        self.process.setToolTip(self.process.currentText())
        session = self.selected()
        available = session is not None and not session.reason
        self.apply.setEnabled(available)
        self.disable.setEnabled(available)
        self.process.setToolTip(session.reason if session and session.reason else self.process.currentText())
        self.update_configuration_button()
        if self.status.actions is not None or time.monotonic() < self.message_until:
            return
        if self.pending and session and not session.reason:
            selected, target, fps, method, started = self.pending
            if session.identity != selected:
                self.pending = None
            elif session.watched == target:
                limit = f'{fps:g} FPS' if fps else 'Unlimited FPS'
                pacing = 'Early · smooth pacing' if method == 'early' else 'Late · low latency'
                self.status.show_message('Applied successfully', f'{limit} · {pacing}')
                self.pending = None
                self.message_until = time.monotonic() + 5
            elif time.monotonic() - started > 3:
                self.status.setText('MangoHud did not switch profiles. Limit unconfirmed.')
                self.pending = None
                self.message_until = time.monotonic() + 6


def main():
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app = QApplication(sys.argv)
    app.setApplicationName('Vela')
    app.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/vela.svg')))
    app.setDesktopFileName('vela')
    window = Window()
    app.aboutToQuit.connect(window.preview.shutdown)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
