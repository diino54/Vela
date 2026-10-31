"""Vela's palette, QSS and cached grid backdrop.

Keep visual values here; the frosted material itself lives in panels.py.
Painting caches are invalidated by window size and device-pixel ratio only.
"""
from pathlib import Path
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPalette, QPainter, QPen, QPixmap, QRadialGradient


def apply_theme(window):
    """Install the existing application palette and stylesheet unchanged."""
    palette = window.palette()
    for role, color in (
        (QPalette.Window, '#0f0f0f'), (QPalette.Base, '#1a1a1a'),
        (QPalette.Button, '#1a1a1a'), (QPalette.Text, '#f5f5f5'),
        (QPalette.WindowText, '#f5f5f5'), (QPalette.ButtonText, '#f5f5f5'),
        (QPalette.Highlight, '#246bce'), (QPalette.HighlightedText, '#ffffff'),
        (QPalette.Light, '#444444'), (QPalette.Mid, '#333333'),
        (QPalette.Dark, '#080808'),
    ):
        palette.setColor(role, QColor(color))
    window.setPalette(palette)
    window.setObjectName('velaWindow')
    window.setStyleSheet("""
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


def paint_window_background(window):
    """Paint the stable dark gradient/grid behind the three main columns."""
    # Cache the static background; hovering controls never rebuilds the grid.
    scale = window.devicePixelRatioF()
    key = (window.width(), window.height(), scale)
    if getattr(window, '_background_key', None) != key:
        canvas = QPixmap(round(window.width() * scale), round(window.height() * scale))
        canvas.setDevicePixelRatio(scale)
        canvas.fill(QColor('#090909'))
        center = QPointF(window.width() * .5, window.height() * .5)
        radius = max(window.width() * .75, window.height() * .95)
        glow = QRadialGradient(center, radius)
        glow.setColorAt(0, QColor('#121212'))
        glow.setColorAt(1, QColor('#090909'))
        painter = QPainter(canvas)
        painter.fillRect(window.rect(), glow)
        grid = QPixmap(canvas.size())
        grid.setDevicePixelRatio(scale)
        grid.fill(Qt.transparent)
        lines = QPainter(grid)
        lines.setPen(QPen(QColor(255, 255, 255, 16), 1))
        for x in range(0, window.width(), 36):
            lines.drawLine(x, 0, x, window.height())
        for y in range(0, window.height(), 36):
            lines.drawLine(0, y, window.width(), y)
        fade = QRadialGradient(center, radius)
        fade.setColorAt(0, QColor(0, 0, 0, 255))
        fade.setColorAt(.45, QColor(0, 0, 0, 130))
        fade.setColorAt(.8, QColor(0, 0, 0, 20))
        fade.setColorAt(1, QColor(0, 0, 0, 0))
        lines.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        lines.fillRect(window.rect(), fade)
        lines.end()
        painter.drawPixmap(0, 0, grid)
        painter.end()
        window._background = canvas
        window._background_key = key
    painter = QPainter(window)
    painter.drawPixmap(0, 0, window._background)



# The modal keeps its own object-name selectors; leaf controls inherit Vela QSS.
FONT_CATALOG_STYLE = """
            QFrame#fontCatalog { background: transparent; }
            QFrame#fontBrowser { background: transparent; border: none; }
            QFrame#fontSidebar { background: rgba(18, 18, 18, 100); border: none; border-radius: 9px; }
            QFrame#fontCatalogContent, QScrollArea#fontCatalogScroll { background: transparent; border: none; }
            QFrame#fontCard { background: #202020; border: 1px solid #303030; border-radius: 9px; }

            QPushButton#fontCategory { background: transparent; border: none; text-align: left; padding: 0 12px; min-height: 36px; }
            QPushButton#fontCategory:checked { background: transparent; color: white; }
            QLabel#fontMeta { color: #909090; font-size: 11px; }
            QPushButton#fontSource { background: transparent; border: none; color: #999999; font-size: 11px; padding: 0; min-height: 20px; }
        """
