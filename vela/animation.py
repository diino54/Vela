"""Small paint-only transitions that leave button geometry and input unchanged."""
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget, QCheckBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect


class ButtonGlow(QObject):
    """A soft pulse for an available save action, with no layout changes."""
    def __init__(self, button):
        super().__init__(button)
        self.button = button
        self.active = False
        self.effect = QGraphicsDropShadowEffect(button)
        self.effect.setOffset(0, 0)
        self.effect.setBlurRadius(24)
        self.effect.setColor(QColor(65, 135, 235, 110))
        self.effect.setEnabled(False)
        button.setGraphicsEffect(self.effect)
        self.motion = QVariantAnimation(self)
        self.motion.setDuration(2400)
        self.motion.setLoopCount(-1)
        self.motion.setEasingCurve(QEasingCurve.InOutSine)
        self.motion.setKeyValueAt(0., 100.)
        self.motion.setKeyValueAt(.5, 175.)
        self.motion.setKeyValueAt(1., 100.)
        self.motion.valueChanged.connect(lambda value: self.effect.setColor(QColor(65, 135, 235, round(value))))
        button.installEventFilter(self)

    def set_active(self, active):
        self.active = bool(active)
        self.sync()

    def sync(self):
        enabled = self.active and self.button.isVisible() and self.button.isEnabled()
        self.effect.setEnabled(enabled)
        if enabled:
            if self.motion.state() != QVariantAnimation.Running:
                self.motion.start()
        else:
            self.motion.stop()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Show, QEvent.Hide, QEvent.EnabledChange):
            self.sync()
        return False


class _Highlight(QWidget):
    def __init__(self, button):
        super().__init__(button)
        self.amount = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(button.rect())
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, round(self.amount)))
        name = self.parentWidget().objectName()
        radius = 3 if name in ('tab', 'fpsStep') else 7
        inset = 5 if name == 'fpsStep' else 1
        if isinstance(self.parentWidget(), QCheckBox):
            painter.drawRoundedRect(0, (self.height() - 16) // 2, 16, 16, 3, 3)
        else:
            painter.drawRoundedRect(self.rect().adjusted(inset, inset, -inset, -inset), radius, radius)


class ButtonMotion(QObject):
    def __init__(self, button):
        super().__init__(button)
        self.button = button
        self.overlay = _Highlight(button)
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.update_amount)
        button.installEventFilter(self)
        button.toggled.connect(lambda _: self.pulse_toggle())

    def pulse_toggle(self):
        self.animation.stop()
        self.animation.setStartValue(32.)
        self.animation.setEndValue(12. if self.button.underMouse() else 0.)
        self.animation.setDuration(340)
        self.animation.start()

    def update_amount(self, amount):
        self.overlay.amount = float(amount)
        self.overlay.update()

    def transition(self, pressed=False):
        pressed_amount = 28 if self.button.objectName() == 'fpsStep' else 0
        target = (pressed_amount if pressed else 12 if self.button.underMouse() else 0) if self.button.isEnabled() else 0
        self.animation.stop()
        self.animation.setStartValue(self.overlay.amount)
        self.animation.setEndValue(float(target))
        self.animation.setDuration(160 if pressed else 320)
        self.animation.start()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Resize:
            self.overlay.setGeometry(self.button.rect())
        elif kind in (QEvent.Enter, QEvent.Leave, QEvent.EnabledChange, QEvent.MouseButtonRelease, QEvent.KeyRelease):
            self.transition()
        elif kind in (QEvent.MouseButtonPress, QEvent.KeyPress):
            self.transition(pressed=True)
        return False


class PageMotion(QObject):
    def __init__(self, parent, layouts):
        super().__init__(parent)
        self.layouts = layouts
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.update_spacing)

    def start(self, *_):
        self.animation.stop()
        self.animation.setStartValue(10.)
        self.animation.setEndValue(0.)
        self.animation.start()

    def update_spacing(self, value):
        for layout in self.layouts:
            layout.setContentsMargins(0, round(value), 0, 0)


class _CardHighlight(QWidget):
    def __init__(self, card):
        super().__init__(card)
        self.amount = 0.
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, event):
        from PySide6.QtGui import QPen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(170, 195, 230, round(100 * self.amount)), 1))
        painter.setBrush(QColor(180, 205, 255, round(7 * self.amount)))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)


class _TileRevealEffect(QGraphicsOpacityEffect):
    def __init__(self, parent):
        super().__init__(parent)
        self.offset = 0.

    def draw(self, painter):
        painter.save()
        painter.translate(0, self.offset)
        super().draw(painter)
        painter.restore()

    def boundingRectFor(self, rect):
        return super().boundingRectFor(rect).adjusted(0, -16, 0, 16)


class CardMotion(QObject):
    """Paint-only hover plus a reusable, cancellable reveal for catalog tiles."""
    def __init__(self, card):
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        super().__init__(card)
        self.card = card
        self.highlight = _CardHighlight(card)
        self.highlight.show()
        self.hover = QVariantAnimation(self)
        self.hover.setEasingCurve(QEasingCurve.OutCubic)
        self.hover.valueChanged.connect(self.paint_hover)
        self.opacity = _TileRevealEffect(card)
        self.opacity.setOpacity(1.)
        self.opacity.setEnabled(False)
        card.setGraphicsEffect(self.opacity)
        self.reveal = QVariantAnimation(self)
        self.reveal.setDuration(420)
        self.reveal.setEasingCurve(QEasingCurve.OutCubic)
        self.reveal.valueChanged.connect(self.update_reveal)
        self.reveal.finished.connect(lambda: self.opacity.setEnabled(False))
        card.installEventFilter(self)

    def update_reveal(self, value):
        self.opacity.offset = -14. * (1. - value)
        self.opacity.setOpacity(value)
        self.card.update()

    def paint_hover(self, value):
        self.highlight.amount = float(value)
        self.highlight.update()

    def pulse(self):
        self.hover.stop()
        self.hover.setStartValue(.85)
        self.hover.setEndValue(1. if self.card.underMouse() else 0.)
        self.hover.setDuration(420)
        self.hover.start()

    def prepare(self):
        self.reveal.stop()
        self.opacity.setEnabled(True)
        self.opacity.offset = -14.
        self.opacity.setOpacity(0.)

    def appear(self):
        self.reveal.setStartValue(self.opacity.opacity())
        self.reveal.setEndValue(1.)
        self.reveal.start()

    def settle(self):
        self.reveal.stop()
        self.opacity.offset = 0.
        self.opacity.setOpacity(1.)
        self.opacity.setEnabled(False)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.highlight.setGeometry(self.card.rect())
            self.highlight.raise_()
        elif event.type() in (QEvent.Enter, QEvent.Leave):
            self.hover.stop()
            self.hover.setStartValue(self.highlight.amount)
            self.hover.setEndValue(1. if event.type() == QEvent.Enter else 0.)
            self.hover.setDuration(180 if event.type() == QEvent.Enter else 280)
            self.hover.start()
        elif event.type() == QEvent.Hide:
            self.settle()
            self.hover.stop()
            self.paint_hover(0.)
        return False
