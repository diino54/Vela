"""Inset frosted modal shell matching the font browser's material and motion.

Capture only the owner's Qt surface, hide its native GL child while open,
and animate a cached panel image rather than scaling live input widgets.
"""

from PySide6.QtCore import QEasingCurve, QEvent, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QWidget

from .panels import FrostedPanel
from .theme import FONT_CATALOG_STYLE


class FrostedModal(QFrame):
    def __init__(self, owner):
        super().__init__(owner)
        self.setObjectName("fontCatalog")
        self.setStyleSheet(FONT_CATALOG_STYLE)
        self.setFocusPolicy(Qt.StrongFocus)
        self.panel = FrostedPanel(self, radius=12)
        self.panel.setObjectName("fontBrowser")
        self.progress = 0.0
        self.closing = False
        self.backdrop = None
        self.proxy = QLabel(self)
        self.proxy.setScaledContents(True)
        self.proxy.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.opacity = QGraphicsOpacityEffect(self.proxy)
        self.proxy.setGraphicsEffect(self.opacity)
        self.motion = QVariantAnimation(self)
        self.motion.setEasingCurve(QEasingCurve.OutCubic)
        self.motion.valueChanged.connect(self.animate)
        self.motion.finished.connect(self.finished)
        self.escape = QShortcut(QKeySequence("Escape"), self)
        self.escape.setContext(Qt.WidgetWithChildrenShortcut)
        self.escape.activated.connect(self.dismiss)
        owner.installEventFilter(self)
        self.hide()

    def fit_panel(self):
        self.setGeometry(self.parentWidget().rect())
        mx, my = max(18, int(self.width() * 0.045)), max(18, int(self.height() * 0.045))
        self.panel.setGeometry(mx, my, self.width() - mx * 2, self.height() - my * 2)
        self.target_rect = self.panel.geometry()

    def animate(self, value):
        self.progress = float(value)
        inset = round(12 * (1 - value))
        dy = round(16 * (1 - value))
        self.proxy.setGeometry(self.target_rect.adjusted(inset, inset + dy, -inset, -inset + dy))
        self.opacity.setOpacity(value)
        self.update()

    def transition(self, target):
        self.motion.stop()
        self.motion.setDuration(400 if target else 260)
        self.motion.setStartValue(self.progress)
        self.motion.setEndValue(target)
        self.motion.start()

    def finished(self):
        if self.closing:
            self.hide()
        else:
            self.proxy.hide()
            self.panel.show()
            self.panel.setFocus()

    def open(self):
        owner = self.parentWidget()
        if not self.isVisible():
            self.backdrop = owner.grab()
            self.disabled_background = [
                widget
                for widget in owner.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)
                if widget is not self and widget.isEnabled()
            ]
            for widget in self.disabled_background:
                widget.setEnabled(False)
            self.restore_preview = owner.preview.isVisible()
            if self.restore_preview:
                owner.preview.hide()
        self.closing = False
        self.motion.stop()
        self.panel.show()
        self.fit_panel()
        self.panel.ensurePolished()
        self.panel.layout().activate()
        self.proxy.setPixmap(self.panel.grab())
        self.panel.hide()
        self.proxy.show()
        self.proxy.raise_()
        self.show()
        self.raise_()
        self.setFocus()
        self.transition(1.0)

    def dismiss(self):
        if self.closing or not self.isVisible():
            return
        self.closing = True
        if self.panel.isVisible():
            self.proxy.setPixmap(self.panel.grab())
        self.panel.hide()
        self.proxy.show()
        self.proxy.raise_()
        self.transition(0.0)

    def hideEvent(self, event):
        self.motion.stop()
        self.proxy.hide()
        owner = self.parentWidget()
        preview = getattr(owner, "preview", None)
        if getattr(self, "restore_preview", False) and preview is not None and not preview.closed:
            preview.show()
        self.restore_preview = False
        for widget in getattr(self, "disabled_background", []):
            widget.setEnabled(True)
        self.disabled_background = []
        self.backdrop = None
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self.fit_panel()
            if self.motion.state() == QVariantAnimation.Running:
                self.animate(self.progress)
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.dismiss()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.backdrop is not None:
            painter.drawPixmap(self.rect(), self.backdrop)
        painter.fillRect(self.rect(), QColor(0, 0, 0, round(170 * self.progress)))
