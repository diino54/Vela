"""Font-browser leaf widgets: wheel-safe style selector, loader and tile.

FontCard receives the catalog coordinator. It owns specimen registration and
input state, while downloads are delegated to catalog.service (GoogleFonts).
It never writes MangoHud configuration itself.
"""
from PySide6.QtCore import QUrl, Qt, QRectF, QVariantAnimation
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices, QPainter, QColor, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QComboBox, QSizePolicy, QWidget, QListView

from .animation import ButtonMotion, CardMotion
from .google_fonts import variant_label


class FontWeightCombo(QComboBox):
    def __init__(self):
        super().__init__()
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setView(view)
        self.setMaxVisibleItems(7)
        self.setStyleSheet('QComboBox { combobox-popup: 0; } QComboBox QAbstractItemView::item { min-height: 30px; }')
    def wheelEvent(self, event):
        # Scrolling the catalog must never change the selected font weight.
        event.ignore()


class FontLoading(QWidget):
    def __init__(self, parent, surface):
        super().__init__(parent)
        self.surface = surface
        self.phase = 0.
        self.motion = QVariantAnimation(self)
        self.motion.setStartValue(0.); self.motion.setEndValue(360.)
        self.motion.setDuration(1100); self.motion.setLoopCount(-1)
        self.motion.valueChanged.connect(self.advance)
        self.hide()

    def advance(self, value): self.phase = value; self.update()

    def showEvent(self, event): self.motion.start(); super().showEvent(event)
    def hideEvent(self, event): self.motion.stop(); super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self); self.surface.paint_underlay(painter, self)
        painter.setRenderHint(QPainter.Antialiasing)
        x, y = self.width()/2, self.height()/2-20
        painter.setPen(QPen(QColor('#303030'), 3)); painter.drawEllipse(QRectF(x-15,y-15,30,30))
        painter.setPen(QPen(QColor('#70a7ee'), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(x-15,y-15,30,30), -round(self.phase*16), 100*16)
        painter.setPen(QColor('#cccccc'))
        painter.drawText(QRectF(0,y+30,self.width(),35),Qt.AlignCenter,'Loading fonts…')



class FontCard(QFrame):
    def __init__(self, catalog, family):
        super().__init__(); self.catalog = catalog; self.family = family; self.busy = False; self.setObjectName('fontCard')
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 12, 14, 12); layout.setSpacing(7)
        name = QLabel(); name.setObjectName('panelTitle'); name.setToolTip(family.name)
        name.setText(name.fontMetrics().elidedText(family.name, Qt.ElideRight, 180)); layout.addWidget(name)
        meta = QLabel(f'{family.category} · {len(family.variants)} styles'); meta.setObjectName('fontMeta'); layout.addWidget(meta)
        self.sample = QLabel('Aa 0123'); self.sample.setMinimumHeight(40); layout.addWidget(self.sample, 1)
        self.weight = FontWeightCombo()
        for variant in family.variants: self.weight.addItem(variant_label(variant), variant)
        default = self.weight.findData('400'); self.weight.setCurrentIndex(max(0, default))
        self.weight.setAccessibleName(family.name + ' weight and style'); layout.addWidget(self.weight)
        self.action = QPushButton(); self.action.setObjectName('apply'); layout.addWidget(self.action)
        self.info = QLabel(); self.info.setObjectName('fontMeta'); self.info.setWordWrap(False); self.info.setFixedHeight(18); layout.addWidget(self.info)
        source = QPushButton('Google Fonts / license ↗'); source.setObjectName('fontSource'); source.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(family.source))); layout.addWidget(source)
        self.motion = CardMotion(self)
        self.button_motions = [ButtonMotion(button) for button in (self.action, source)]
        self.weight.currentTextChanged.connect(self.weight_changed); self.action.clicked.connect(self.activate); self.refresh(load=False)

    def variant(self): return self.weight.currentData()

    def path(self): return self.family.path(self.variant())

    def weight_changed(self):
        self.catalog.font_updates.append((self.family.slug, self.variant(), True, '')); self.catalog.registration_timer.start()
        self.motion.pulse(); self.catalog.preview_timer.start()

    def load_preview(self):
        path = self.path()
        if not path.is_file(): path = self.family.preview_path(self.variant())
        if not path.is_file(): return False
        if str(path) not in self.catalog.font_ids:
            identifier = QFontDatabase.addApplicationFont(str(path))
            if identifier < 0:
                path.unlink(missing_ok=True); return False
            self.catalog.font_ids[str(path)] = identifier
        identifier = self.catalog.font_ids[str(path)]
        families = QFontDatabase.applicationFontFamilies(identifier)
        if not families: return False
        weight = int(self.variant().rstrip('i'))
        italic = self.variant().endswith('i')
        font = QFont(families[0], 20); font.setWeight(QFont.Weight(weight)); font.setItalic(italic); self.sample.setFont(font)
        self.sample.setStyleSheet('font-family: "' + families[0].replace('"','') + '"; font-size: 23px; font-weight: ' + str(weight) + '; font-style: ' + ('italic' if italic else 'normal') + ';')
        return True

    def refresh(self, load=True):
        preview = self.load_preview() if load else False
        ready = self.path().is_file()
        if not preview: self.sample.setStyleSheet('font-family: monospace; font-size: 23px;')
        if not self.busy: self.action.setText('Use font' if ready else 'Download font')
        self.info.setText('Downloaded · actual preview' if ready else 'Actual preview · not installed' if preview else 'Loading preview…')

    def activate(self):
        if self.busy: return
        if self.path().is_file() and self.load_preview():
            self.catalog.apply_font(self.catalog.key, str(self.path())); self.catalog.dismiss(); return
        self.busy = True; self.weight.setEnabled(False); self.action.setEnabled(False); self.action.setText('Downloading…'); self.info.setText('Downloading font and license…')
        self.catalog.service.download(self.family, self.variant())
