"""Shared read-only metric cards and line icons for HDR and ReShade."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from .animation import CardMotion

ICONS = {
    "game": '<path d="M8 7h8c3 0 5 3 5 9 0 3-3 3-5 0H8c-2 3-5 3-5 0 0-6 2-9 5-9Z"/><path d="M7 10v5m-2.5-2.5h5M16 11h.01M18 14h.01"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3Z"/>',
    "edit": '<path d="m14 5 5 5M4 20l5-1L21 7l-5-5L4 14Z"/>',
    "monitor": '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "session": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 8h18M8 8v13"/>',
    "gpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    "color": '<circle cx="9" cy="9" r="5"/><circle cx="15" cy="9" r="5"/><circle cx="12" cy="15" r="5"/>',
    "refresh": '<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
    "scale": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 16l8-8m-5 0h5v5"/>',
}


def metric_icon(name):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        'fill="none" stroke="#9fbce3" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        + ICONS.get(name, ICONS["monitor"])
        + "</svg>"
    )
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return pixmap


class MetricCard(QFrame):
    def __init__(self, title, value, icon):
        super().__init__()
        self.setObjectName("fontCard")
        self.setMinimumHeight(124)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        symbol = QLabel()
        symbol.setPixmap(metric_icon(icon))
        layout.addWidget(symbol)
        label = QLabel(title)
        label.setObjectName("fontMeta")
        label.setWordWrap(True)
        layout.addWidget(label)
        text = QLabel(str(value))
        text.setTextFormat(Qt.PlainText)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.setStyleSheet("color: #f2f2f2; font-size: 17px; font-weight: 600;")
        layout.addWidget(text)
        layout.addStretch()
        self.setAccessibleName(f"{title}: {value}")
        self.motion = CardMotion(self)


class MetricGrid(QWidget):
    def __init__(self, metrics):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.cards = [MetricCard(*metric) for metric in metrics]
        self.columns = 0
        self.reflow()

    def reflow(self):
        columns = 3 if self.width() >= 650 else 2 if self.width() >= 400 else 1
        if columns == self.columns:
            return
        for column in range(self.columns):
            self.grid.setColumnStretch(column, 0)
        while self.grid.count():
            self.grid.takeAt(0)
        self.columns = columns
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)

    def resizeEvent(self, event):
        self.reflow()
        super().resizeEvent(event)
