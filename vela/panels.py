"""Shared frosted surface used by Vela's settings panels and dialogs."""
from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame
from .background import frosted_pixels


class FrostedPanel(QFrame):
    def __init__(self, parent=None, radius=6):
        super().__init__(parent)
        self.radius = radius
        pixels = frosted_pixels(268, 576, .35, 24)
        self.texture = QImage(pixels, 268, 576, QImage.Format_RGB888).copy()

    def paint_underlay(self, painter, child):
        """Paint a matching part of the surface beneath a temporary cover."""
        origin = child.mapTo(self, QPoint())
        sx, sy = self.texture.width()/max(1,self.width()), self.texture.height()/max(1,self.height())
        source = QRectF(origin.x()*sx,origin.y()*sy,child.width()*sx,child.height()*sy)
        painter.drawImage(QRectF(child.rect()),self.texture,source)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), self.radius, self.radius)
        painter.setClipPath(shape)
        painter.drawImage(self.rect(), self.texture)
        painter.setClipping(False)
        painter.setPen(QPen(QColor('#303030'), 1))
        painter.drawPath(shape)
