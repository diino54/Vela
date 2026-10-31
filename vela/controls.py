"""Reusable inputs and scroll feedback, independent of the main window.

Wheel input never changes numeric/combo values. SettingsScroll paints edge
fades; NumberControl owns the custom FPS/appearance spin-box chrome.
"""
from PySide6.QtCore import QPointF, QRectF, Qt, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QWidget, QListView, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QStyleOptionComboBox, QStyleOptionFrame, QStylePainter

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
