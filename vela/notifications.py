"""In-app messages and save choices, independent of the preview layout."""
from pathlib import Path

from PySide6.QtCore import QObject, Property, QEvent, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLayout,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)


class ElidedLabel(QLabel):
    """Keep long application and file names within the card's width."""
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self.full_text = text
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setToolTip(text)
        self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.ElideMiddle, self.width()))


class WindowFade(QObject):
    """Fade the native surface, including its painted background."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.amount = 1.

    def opacity(self):
        return self.amount

    def setOpacity(self, amount):
        self.amount = float(amount)
        if QApplication.platformName() != 'offscreen':
            self.window.setWindowOpacity(self.amount)

    value = Property(float, opacity, setOpacity)


class Notification(QFrame):
    GLOW_MARGIN = 10
    choice_closed = Signal()
    presenting = Signal(object)
    dismissed = Signal()
    opacity_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.setObjectName('notification')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        self.highlight = 0.
        self.glow_strength = .15
        self.glow_motion = QVariantAnimation(self)
        self.glow_motion.setDuration(2400)
        self.glow_motion.setLoopCount(-1)
        self.glow_motion.setEasingCurve(QEasingCurve.InOutSine)
        self.glow_motion.setKeyValueAt(0., .15)
        self.glow_motion.setKeyValueAt(.5, .75)
        self.glow_motion.setKeyValueAt(1., .15)
        self.glow_motion.valueChanged.connect(self.set_glow_strength)
        self.exiting = False
        self.bottom_inset = 20
        self.hover_motion = QVariantAnimation(self)
        self.hover_motion.setDuration(120)
        self.hover_motion.valueChanged.connect(self.set_highlight)
        self.setStyleSheet('''
            QFrame#notification { background: #202020; border: 1px solid #414141; border-radius: 10px; }
            QFrame#notification QLabel { background: transparent; border: none; }
            QLabel#noticeTitle { color: #eeeeee; font-size: 13px; font-weight: 600; }
            QLabel#noticeDetail { color: #ababab; font-size: 12px; }
            QPushButton#destination { background: #292929; border: 1px solid #414141;
                border-radius: 6px; text-align: left; padding: 0; min-height: 64px; }
            QPushButton#destination:hover { background: #333333; border-color: #666666; }
            QPushButton#destination:focus { border-color: #6095de; }
            QPushButton#destination[recommended="true"] { background: #232c39; border-color: #3e608c; }
            QPushButton#destination[recommended="true"]:hover { background: #2b3749; border-color: #6095de; }
            QPushButton#noticeCancel { background: transparent; border: none; color: #b0b0b0;
                min-height: 26px; padding: 0 8px; }
            QPushButton#noticeCancel:hover { background: #303030; color: #eeeeee; }
        ''')
        self.layout_box = QVBoxLayout(self)
        # The native surface must be allowed to shrink after a choice card.
        self.layout_box.setSizeConstraint(QLayout.SetNoConstraint)
        self.layout_box.setContentsMargins(28, 26, 28, 22)
        self.layout_box.setSpacing(8)
        self.title = QLabel()
        self.title.setObjectName('noticeTitle')
        self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True)
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detail = QLabel()
        self.detail.setObjectName('noticeDetail')
        self.detail.setTextFormat(Qt.PlainText)
        self.detail.setWordWrap(True)
        self.detail.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.layout_box.addWidget(self.title)
        self.layout_box.addWidget(self.detail)
        self.actions = None
        self.fade = WindowFade(self)
        self.motion = QPropertyAnimation(self.fade, b'value', self)
        self.motion.setDuration(420)
        self.motion.setEasingCurve(QEasingCurve.InOutCubic)
        self.motion.valueChanged.connect(self.reposition)
        self.motion.valueChanged.connect(lambda value: self.opacity_changed.emit(float(value)))
        self.motion.finished.connect(self.finish_transition)
        self.expiry = QTimer(self)
        self.expiry.setSingleShot(True)
        self.expiry.timeout.connect(self.dismiss)
        self.generation = 0
        QApplication.instance().applicationStateChanged.connect(self.application_state_changed)
        self.hide()

    def attach_to(self, parent):
        # A transient native tool surface can stack over a foreign GL child.
        # It has no title bar or taskbar entry and follows the owning app.
        self.setParent(parent, Qt.Tool | Qt.FramelessWindowHint)
        parent.installEventFilter(self)
        parent.window().installEventFilter(self)

    def application_state_changed(self, state):
        if state != Qt.ApplicationActive:
            self.hide_immediately()

    def hide_immediately(self, force=False):
        if not force and self.isHidden() and self.actions is None:
            return
        self.generation += 1
        self.motion.stop()
        self.hover_motion.stop()
        self.expiry.stop()
        self.hide()
        self.clear_actions()
        self.exiting = False
        self.fade.setOpacity(0.)
        self.dismissed.emit()

    def check_owner_focus(self):
        owner = self.parentWidget().window() if self.parentWidget() else None
        active = QApplication.activeWindow()
        while active is not None:
            if active in (self, owner):
                return
            active = active.parentWidget()
        self.hide_immediately()

    def set_highlight(self, value):
        self.highlight = float(value)
        self.update()

    def set_glow_strength(self, value):
        self.glow_strength = float(value)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.glow_motion.start()

    def hideEvent(self, event):
        self.glow_motion.stop()
        super().hideEvent(event)

    def animate_highlight(self, target):
        self.hover_motion.stop()
        self.hover_motion.setStartValue(self.highlight)
        self.hover_motion.setEndValue(target)
        self.hover_motion.start()

    def enterEvent(self, event):
        if not self.exiting:
            self.animate_highlight(.15)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.exiting:
            self.animate_highlight(0.)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.hover_motion.stop()
            self.set_highlight(1.)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.dismiss(quick=True)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dismiss(quick=True)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        # Paint an opaque card explicitly; translucent native windows must not
        # depend on a stylesheet or an offscreen graphics effect for their fill.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        card = QRectF(self.rect()).adjusted(self.GLOW_MARGIN + 1, self.GLOW_MARGIN + 1,
                                          -self.GLOW_MARGIN - 1, -self.GLOW_MARGIN - 1)
        painter.setBrush(Qt.NoBrush)
        for spread in range(self.GLOW_MARGIN, 0, -1):
            falloff = (1 - spread / (self.GLOW_MARGIN + 1)) ** 2
            alpha = round((12 + 28 * self.glow_strength) * falloff)
            painter.setPen(QPen(QColor(65, 135, 235, alpha), 1.5))
            painter.drawRoundedRect(card.adjusted(-spread, -spread, spread, spread),
                                    9 + spread, 9 + spread)
        mix = self.highlight
        background = QColor(round(32 + 2 * mix), round(32 + 20 * mix), round(32 + 42 * mix))
        border = QColor(round(65 + 10 * mix), round(65 + 35 * mix), round(65 + 70 * mix))
        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(card, 9, 9)

    def setText(self, text):
        self.show_message(text)

    def text(self):
        return self.title.text()

    def clear_actions(self):
        if self.actions is not None:
            self.layout_box.removeWidget(self.actions)
            self.actions.hide()
            self.actions.deleteLater()
            self.actions = None
            self.layout_box.invalidate()
            self.setMinimumSize(0, 0)
            self.choice_closed.emit()

    def show_message(self, text, details=None, duration=3500):
        self.clear_actions()
        self.title.setText(text)
        self.title.setToolTip(text)
        # File locations belong in a tooltip; the message stays short and readable.
        self.detail.setText(details.name if isinstance(details, Path) else str(details or ''))
        self.detail.setToolTip(str(details or ''))
        self.detail.setVisible(bool(details))
        self.present(duration)

    def show_choice(self, application, global_path, profile_path, on_global, on_profile, on_cancel):
        self.clear_actions()
        self.title.setText('Save configuration')
        self.title.setToolTip('')
        self.detail.setText('Choose where to save these appearance settings.')
        self.detail.setToolTip('')
        self.detail.show()
        self.actions = QWidget(self)
        choices = QVBoxLayout(self.actions)
        choices.setContentsMargins(0, 4, 0, 0)
        choices.setSpacing(8)
        action = 'Update' if profile_path.exists() else 'Create'
        for title, description, path, callback, recommended in (
            ('This application', f'{action} profile · {application}', profile_path, on_profile, True),
            ('Global configuration', 'Use for applications without their own profile', global_path, on_global, False),
        ):
            button = QPushButton(self.actions)
            button.setObjectName('destination')
            button.setProperty('recommended', recommended)
            button.setAccessibleName(f'{title}: {description}')
            button.setToolTip(str(path))
            button.setMinimumHeight(62)
            row = QVBoxLayout(button)
            row.setContentsMargins(12, 9, 12, 9)
            row.setSpacing(3)
            heading = QLabel(title)
            heading.setObjectName('noticeTitle')
            subtitle = ElidedLabel(description)
            subtitle.setObjectName('noticeDetail')
            for label in (heading, subtitle):
                label.setAttribute(Qt.WA_TransparentForMouseEvents)
                row.addWidget(label)
            button.clicked.connect(callback)
            choices.addWidget(button)
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton('Cancel')
        cancel.setObjectName('noticeCancel')
        cancel.clicked.connect(on_cancel)
        footer.addWidget(cancel)
        choices.addLayout(footer)
        self.layout_box.addWidget(self.actions)
        self.present(0)

    def present(self, duration):
        self.expiry.stop()
        self.motion.stop()
        self.generation += 1
        generation = self.generation
        def ready():
            if generation != self.generation:
                return False
            self.present_now(duration)
            return True
        self.presenting.emit(ready)

    def present_now(self, duration):
        if (QApplication.platformName() != 'offscreen'
                and QApplication.applicationState() != Qt.ApplicationActive):
            self.hide_immediately(force=True)
            return
        self.exiting = False
        self.hover_motion.stop()
        self.set_highlight(0.)
        self.motion.setDuration(420)
        opacity = self.fade.opacity() if self.isVisible() else 0.
        self.fade.setOpacity(opacity)
        self.reposition()
        self.show()
        self.raise_()
        self.motion.setStartValue(opacity)
        self.motion.setEndValue(1.)
        self.motion.start()
        if duration:
            self.expiry.start(duration)

    def dismiss(self, quick=False):
        if self.exiting:
            return
        self.exiting = True
        self.generation += 1
        self.expiry.stop()
        if self.actions is not None:
            self.actions.setEnabled(False)
        self.motion.stop()
        self.motion.setDuration(150 if quick else 420)
        self.motion.setStartValue(self.fade.opacity())
        self.motion.setEndValue(0.)
        self.motion.start()

    def reposition(self, *_):
        if self.exiting:
            return
        if self.parentWidget():
            parent = self.parentWidget()
            width = max(1, min(460, parent.width() - 32))
            self.layout_box.invalidate()
            margins = self.layout_box.contentsMargins()
            content_width = max(1, width - margins.left() - margins.right())
            rows = [self.title]
            if not self.detail.isHidden():
                rows.append(self.detail)
            if self.actions is not None:
                rows.append(self.actions)
            height = margins.top() + margins.bottom() + self.layout_box.spacing() * (len(rows) - 1)
            for row in rows:
                row_height = row.heightForWidth(content_width)
                height += max(0, row_height if row_height >= 0 else row.sizeHint().height())
            self.setMinimumSize(0, 0)
            offset = round(12 * (1 - self.fade.opacity()))
            position = parent.rect().topLeft()
            position.setX((parent.width() - width) // 2)
            position.setY(max(8, parent.height() - height - self.bottom_inset + offset))
            if self.isWindow():
                position = parent.mapToGlobal(position)
            self.setGeometry(position.x(), position.y(), width, height)
            self.layout_box.activate()

    def eventFilter(self, watched, event):
        owner = self.parentWidget().window() if self.parentWidget() else None
        if watched is owner:
            if event.type() == QEvent.Hide or (event.type() == QEvent.WindowStateChange and owner.isMinimized()):
                self.hide_immediately()
            elif event.type() == QEvent.WindowDeactivate:
                QTimer.singleShot(50, self, self.check_owner_focus)
        if event.type() in (QEvent.Resize, QEvent.Move) and watched in (self.parentWidget(), owner):
            self.reposition()
        return super().eventFilter(watched, event)

    def finish_transition(self):
        if self.fade.opacity() == 0:
            self.hide()
            self.clear_actions()
            self.exiting = False
            self.dismissed.emit()
