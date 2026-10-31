"""Downloadable static HUD fonts; downloads never block the UI thread."""
from pathlib import Path
from PySide6.QtCore import QEvent, QUrl, Qt, QRectF, QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices, QShortcut, QKeySequence, QPainter, QColor, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QScrollArea, QGridLayout, QLineEdit, QButtonGroup, QSizePolicy, QWidget, QGraphicsOpacityEffect, QListView

from .animation import ButtonMotion, CardMotion
from .panels import FrostedPanel

from .google_fonts import GoogleFonts, font_directory, variant_label


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


class FontCatalog(QFrame):
    def __init__(self, window, apply_font):
        super().__init__(window)
        self.apply_font = apply_font
        self.service = GoogleFonts(self)
        self.page = 0
        self.page_size = 24
        self.card_cache = {}
        self.loading_fonts = False
        self.load_generation = 0
        self.font_updates = []
        self.registration_timer = QTimer(self); self.registration_timer.setInterval(20)
        self.registration_timer.timeout.connect(self.register_next_font)
        self.seen_cards = set()
        self.font_ids = {}
        self.backdrop = None
        self.category = 'All fonts'
        self.modal_progress = 0.
        self.closing = False
        self.reveal_generation = 0
        self.modal_motion = QVariantAnimation(self)
        self.modal_motion.setEasingCurve(QEasingCurve.OutCubic)
        self.modal_motion.valueChanged.connect(self.update_modal)
        self.modal_motion.finished.connect(self.finish_modal)
        self.nav_motion = QVariantAnimation(self)
        self.nav_motion.setDuration(340)
        self.nav_motion.setEasingCurve(QEasingCurve.OutCubic)
        self.setObjectName('fontCatalog')
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("""
            QFrame#fontCatalog { background: transparent; }
            QFrame#fontBrowser { background: transparent; border: none; }
            QFrame#fontSidebar { background: rgba(18, 18, 18, 100); border: none; border-radius: 9px; }
            QFrame#fontCatalogContent, QScrollArea#fontCatalogScroll { background: transparent; border: none; }
            QFrame#fontCard { background: #202020; border: 1px solid #303030; border-radius: 9px; }

            QPushButton#fontCategory { background: transparent; border: none; text-align: left; padding: 0 12px; min-height: 36px; }
            QPushButton#fontCategory:checked { background: transparent; color: white; }
            QLabel#fontMeta { color: #909090; font-size: 11px; }
            QPushButton#fontSource { background: transparent; border: none; color: #999999; font-size: 11px; padding: 0; min-height: 20px; }
        """)
        self.panel = FrostedPanel(self, radius=12); self.panel.setObjectName('fontBrowser')
        layout = QVBoxLayout(self.panel); layout.setContentsMargins(22, 18, 22, 22); layout.setSpacing(18)
        header = QHBoxLayout()
        self.title = QLabel('Font presets'); self.title.setObjectName('panelTitle'); header.addWidget(self.title, 1)
        close = QPushButton('Close  ×'); close.clicked.connect(self.dismiss); header.addWidget(close); layout.addLayout(header)
        body = QHBoxLayout(); body.setSpacing(22); layout.addLayout(body, 1)
        sidebar = QFrame(); sidebar.setObjectName('fontSidebar'); sidebar.setFixedWidth(164)
        nav = QVBoxLayout(sidebar); nav.setContentsMargins(10, 16, 10, 16); nav.setSpacing(5)
        heading = QLabel('CATEGORIES'); heading.setObjectName('fontMeta'); nav.addWidget(heading); nav.addSpacing(10)
        self.categories = QButtonGroup(self); self.category_buttons = {}
        for category in ('All fonts', 'Monospace', 'Sans serif', 'Serif', 'Display', 'Handwriting', 'Downloaded'):
            button = QPushButton(category); button.setObjectName('fontCategory'); button.setCheckable(True)
            self.categories.addButton(button); self.category_buttons[category] = button; nav.addWidget(button)
            button.clicked.connect(lambda checked=False, category=category: self.select_category(category))
        self.category_buttons['All fonts'].setChecked(True); nav.addStretch()
        self.nav_indicator = QFrame(sidebar)
        self.nav_indicator.setStyleSheet('background: #353535; border: none; border-radius: 7px;')
        self.nav_indicator.lower()
        self.nav_motion.valueChanged.connect(self.nav_indicator.setGeometry)
        note = QLabel('Google Fonts\nFull catalog\n\nFonts cached locally'); note.setObjectName('fontMeta'); nav.addWidget(note)
        body.addWidget(sidebar)
        right = QVBoxLayout(); right.setSpacing(14); body.addLayout(right, 1)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search fonts…'); self.search.setAccessibleName('Search fonts')
        tools = QHBoxLayout(); tools.addWidget(self.search, 1)
        self.sort = QComboBox(); self.sort.addItems(('Popular', 'Name A–Z')); self.sort.setAccessibleName('Sort fonts'); tools.addWidget(self.sort)
        self.reload = QPushButton('Refresh'); self.reload.clicked.connect(lambda: self.service.refresh(True)); tools.addWidget(self.reload)
        right.addLayout(tools)
        self.catalog_status = QLabel(f'Google Fonts · {len(self.service.families):,} families · cached catalog'); self.catalog_status.setObjectName('fontMeta'); right.addWidget(self.catalog_status)
        self.result = QLabel(); self.result.setObjectName('fontMeta'); right.addWidget(self.result)
        self.scroll = QScrollArea(); self.scroll.setObjectName('fontCatalogScroll'); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QFrame(); self.content.setObjectName('fontCatalogContent')
        self.grid = QGridLayout(self.content); self.grid.setContentsMargins(0, 0, 8, 0); self.grid.setSpacing(14); self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.cards = []
        self.empty = QLabel('No matching fonts. Try another category or search.'); self.empty.setWordWrap(True); self.empty.setParent(self.content); self.empty.hide()
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setWidget(self.content); right.addWidget(self.scroll, 1)
        self.loading = FontLoading(self.scroll.viewport(), self.panel)
        self.scroll.viewport().installEventFilter(self)
        self.preview_timer = QTimer(self); self.preview_timer.setSingleShot(True); self.preview_timer.setInterval(160)
        self.preview_timer.timeout.connect(self.update_visible_previews)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _: self.preview_timer.start())
        self.search.textChanged.connect(self.reset_results)
        self.sort.currentIndexChanged.connect(self.reset_results)
        pages = QHBoxLayout()
        self.previous = QPushButton('← Previous'); self.previous.clicked.connect(lambda: self.change_page(-1)); pages.addWidget(self.previous)
        self.page_label = QLabel(); self.page_label.setAlignment(Qt.AlignCenter); pages.addWidget(self.page_label, 1)
        self.next = QPushButton('Next →'); self.next.clicked.connect(lambda: self.change_page(1)); pages.addWidget(self.next)
        right.addLayout(pages)
        self.escape = QShortcut(QKeySequence('Escape'), self); self.escape.setContext(Qt.WidgetWithChildrenShortcut); self.escape.activated.connect(self.dismiss)
        self.modal_image = QLabel(self)
        self.modal_image.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.modal_image.setScaledContents(True)
        self.modal_opacity = QGraphicsOpacityEffect(self.modal_image)
        self.modal_image.setGraphicsEffect(self.modal_opacity)
        self.modal_image.hide()
        self.grid_image = QLabel(self.scroll.viewport())
        self.grid_image.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.grid_opacity = QGraphicsOpacityEffect(self.grid_image)
        self.grid_image.setGraphicsEffect(self.grid_opacity)
        self.grid_image.hide()
        self.grid_motion = QVariantAnimation(self)
        self.grid_motion.setDuration(320)
        self.grid_motion.setEasingCurve(QEasingCurve.OutCubic)
        self.grid_motion.valueChanged.connect(self.update_grid_transition)
        self.grid_motion.finished.connect(self.grid_image.hide)
        self.button_motions = [ButtonMotion(button) for button in self.panel.findChildren(QPushButton)]
        self.service.catalog_changed.connect(self.catalog_updated)
        self.service.status_changed.connect(self.catalog_status.setText)
        self.service.font_ready.connect(self.font_ready)
        self.service.font_failed.connect(self.font_failed)
        window.installEventFilter(self)
        self.hide()

    def select_category(self, category):
        if category == self.category: return
        if self.isVisible() and self.panel.isVisible():
            self.grid_motion.stop()
            self.grid_image.hide()
            self.grid_image.setPixmap(self.scroll.viewport().grab())
            self.grid_image.setGeometry(self.scroll.viewport().rect())
            self.grid_opacity.setOpacity(1.)
            self.grid_image.show(); self.grid_image.raise_()
            self.grid_motion.setStartValue(0.); self.grid_motion.setEndValue(1.); self.grid_motion.start()
        self.category = category
        self.page = 0
        self.category_buttons[category].setChecked(True)
        self.move_indicator(True)
        self.reflow(animate=True)
        self.scroll.verticalScrollBar().setValue(0)

    def move_indicator(self, animated=False):
        target = self.category_buttons[self.category].geometry()
        self.nav_motion.stop()
        if animated and self.nav_indicator.geometry().isValid():
            self.nav_motion.setStartValue(self.nav_indicator.geometry()); self.nav_motion.setEndValue(target); self.nav_motion.start()
        else: self.nav_indicator.setGeometry(target)

    def update_grid_transition(self, value):
        self.grid_opacity.setOpacity(1. - value)
        self.grid_image.move(-round(16 * value), 0)

    def reset_results(self, *_):
        self.page = 0
        self.reflow(animate=True)
        self.scroll.verticalScrollBar().setValue(0)

    def catalog_updated(self):
        if self.loading_fonts:
            self._catalog_pending = True; return
        self.reflow(animate=self.isVisible() and not self.loading_fonts)

    def change_page(self, amount):
        self.page = max(0, self.page + amount)
        self._grid_signature = None
        self.reflow(animate=True)
        self.scroll.verticalScrollBar().setValue(0)

    def font_ready(self, slug, variant, preview, path):
        self.font_updates.append((slug, variant, preview, path))
        self.registration_timer.start()

    def register_next_font(self):
        if not self.font_updates:
            self.registration_timer.stop(); return
        slug, variant, preview, path = self.font_updates.pop(0)
        card = self.card_cache.get(slug)
        if card is not None:
            if not preview:
                card.busy = False; card.weight.setEnabled(True); card.action.setEnabled(True)
            if card.variant() == variant: card.refresh(); card.motion.pulse()
        if self.category == 'Downloaded' and not preview:
            self._grid_signature = None; self.reflow(animate=True)

    def font_failed(self, slug, variant, preview, message):
        card = self.card_cache.get(slug)
        if card is not None and card.variant() == variant:
            if preview and not card.busy:
                card.info.setText('Preview unavailable · download to use')
            elif not preview:
                card.busy = False; card.weight.setEnabled(True); card.action.setEnabled(True)
                card.action.setText('Retry download'); card.info.setText('Download failed · retry')
            card.info.setToolTip(message)

    def update_visible_previews(self):
        if not self.isVisible() or self.closing or not self.panel.isVisible(): return
        self.service.preview_queue.clear()
        arriving = []
        for card in self.visible_cards:
            if self.scroll.viewport().rect().intersects(card.geometry().translated(0,-self.scroll.verticalScrollBar().value())):
                self.service.queue_preview(card.family, card.variant())
                if card.family.slug not in self.seen_cards:
                    self.seen_cards.add(card.family.slug)
                    arriving.append(card)
        generation = self.reveal_generation
        for index, card in enumerate(arriving):
            self.schedule_card_reveal(card, index, generation)

    def schedule_card_reveal(self, card, index, generation):
        card.motion.prepare()
        def reveal():
            if generation == self.reveal_generation and self.isVisible() and not self.closing and not card.isHidden():
                card.motion.appear()
        QTimer.singleShot(index * 65, reveal)

    def reveal_cards(self):
        self.reveal_generation += 1
        generation = self.reveal_generation
        self.seen_cards.clear()
        self.grid.activate()
        order = 0
        for card in getattr(self, 'visible_cards', []):
            onscreen = self.scroll.viewport().rect().intersects(card.geometry().translated(0,-self.scroll.verticalScrollBar().value()))
            if not onscreen:
                card.motion.settle(); continue
            self.seen_cards.add(card.family.slug)
            self.schedule_card_reveal(card, order, generation)
            order += 1
        self.preview_timer.start()

    def matching_families(self):
        query = self.search.text().strip().casefold()
        downloaded = {p.name for p in font_directory().iterdir() if p.is_dir() and any(p.glob('*.ttf'))} if self.category == 'Downloaded' and font_directory().is_dir() else set()
        families = [family for family in self.service.families if query in family.name.casefold() and
                    (self.category == 'All fonts' or family.category == self.category or
                     (self.category == 'Downloaded' and (family.slug in downloaded or family.legacy_slug in downloaded)))]
        if self.sort.currentIndex() == 1: families.sort(key=lambda family: family.name.casefold())
        return families

    def reflow(self, *_, animate=False):
        if not hasattr(self, 'cards'): return
        if self.loading_fonts and not getattr(self, '_preparing_fonts', False): return
        query = self.search.text().strip().casefold()
        families = self.matching_families()
        page_count = max(1, (len(families) + self.page_size - 1) // self.page_size)
        self.page = min(self.page, page_count - 1)
        selected = families[self.page*self.page_size:(self.page+1)*self.page_size]
        signature = (self.category, query, self.page, tuple(family for family in selected), self.scroll.viewport().width())
        if signature == getattr(self, '_grid_signature', None): return
        self._grid_signature = signature
        self.reveal_generation += 1
        while self.grid.count(): self.grid.takeAt(0)
        for card in self.cards: card.hide()
        self.empty.hide()
        self.cards = []
        for family in selected:
            card = self.card_cache.get(family.slug)
            if card is None:
                card = FontCard(self, family); self.card_cache[family.slug] = card
            self.cards.append(card)
        # Keep a few visited pages and in-flight downloads, not thousands of widgets.
        if len(self.card_cache)>96:
            for slug, card in list(self.card_cache.items()):
                if card not in self.cards and not card.busy:
                    card.deleteLater(); del self.card_cache[slug]
        self.visible_cards = self.cards
        width = max(200, self.scroll.viewport().width() - 8)
        self.columns = max(1, width // 234)
        card_width = min(290, (width - (self.columns - 1) * 14) // self.columns)
        for index, card in enumerate(self.cards):
            card.setFixedSize(card_width, 258); self.grid.addWidget(card, index // self.columns, index % self.columns); card.show()
        if not self.cards: self.grid.addWidget(self.empty, 0, 0); self.empty.show()
        self.result.setText(f'{len(families):,} families · {self.category}')
        self.page_label.setText(f'{self.page + 1} / {page_count}')
        self.previous.setEnabled(self.page>0); self.next.setEnabled(self.page<page_count-1)
        if animate and self.panel.isVisible() and not self.closing and not self.loading_fonts: self.reveal_cards()
        elif self.isVisible(): self.preview_timer.start()

    def fit_panel(self):
        mx = max(18, int(self.width() * .045)); my = max(18, int(self.height() * .045))
        self.panel.setGeometry(mx, my, self.width() - mx * 2, self.height() - my * 2)
        self.target_rect = self.panel.geometry()
        if not self.loading_fonts: QTimer.singleShot(0, self.reflow)
        QTimer.singleShot(0, self.move_indicator)

    def update_modal(self, value):
        self.modal_progress = float(value)
        target = self.target_rect
        inset = round(12 * (1. - value))
        rect = target.adjusted(inset, inset + round(16 * (1. - value)), -inset, -inset + round(16 * (1. - value)))
        self.modal_image.setGeometry(rect)
        self.modal_opacity.setOpacity(value)
        self.update()

    def finish_modal(self):
        if self.closing:
            self.hide()
        else:
            self.modal_image.hide(); self.panel.show(); self.search.setFocus()
            if self.loading_fonts:
                self.loading.setGeometry(self.scroll.viewport().rect()); self.loading.show(); self.loading.raise_()
                generation = self.load_generation
                QTimer.singleShot(0, lambda: self.prepare_fonts(generation))
            else: self.reveal_cards()

    def prepare_fonts(self, generation):
        if generation != self.load_generation or self.closing or not self.isVisible(): return
        families = self.matching_families()
        pending = [family for family in families[self.page*self.page_size:(self.page+1)*self.page_size]
                   if family.slug not in self.card_cache]
        self.build_loading_batch(generation, pending)

    def build_loading_batch(self, generation, pending):
        if generation != self.load_generation or self.closing or not self.isVisible(): return
        for family in pending[:3]:
            card = FontCard(self, family); card.setParent(self.content); card.hide(); self.card_cache[family.slug] = card
        if len(pending)>3:
            QTimer.singleShot(12, lambda: self.build_loading_batch(generation, pending[3:])); return
        self._preparing_fonts = True
        try: self.reflow()
        finally: self._preparing_fonts = False
        self.grid.activate()
        for card in self.cards:
            if self.scroll.viewport().rect().intersects(card.geometry().translated(0,-self.scroll.verticalScrollBar().value())):
                self.font_updates.append((card.family.slug, card.variant(), True, ''))
        self.registration_timer.start()
        self.update_visible_previews()
        self.service.refresh()
        # Give cached specimens and fast network responses a short preparation window.
        QTimer.singleShot(650, lambda: self.finish_loading(generation, 0))

    def finish_loading(self, generation, retry):
        if generation != self.load_generation or self.closing or not self.isVisible(): return
        if retry < 5 and (self.font_updates or self.service.active_previews):
            QTimer.singleShot(120, lambda: self.finish_loading(generation, retry+1)); return
        self.loading_fonts = False
        if getattr(self, '_catalog_pending', False):
            self._catalog_pending = False; self.reflow()
        self.loading.hide()
        self.reveal_cards()

    def start_modal(self, target):
        self.modal_motion.stop()
        self.panel.setEnabled(target == 1.)
        self.modal_motion.setDuration(400 if target == 1. else 260)
        self.modal_motion.setStartValue(self.modal_progress)
        self.modal_motion.setEndValue(target)
        self.modal_motion.start()

    def dismiss(self):
        if not self.isVisible() or self.closing: return
        self.closing = True
        self.load_generation += 1
        self.reveal_generation += 1
        self.grid_motion.stop(); self.grid_image.hide()
        for card in self.cards: card.motion.settle()
        if self.panel.isVisible():
            self.modal_image.setPixmap(self.panel.grab())
        self.panel.hide()
        self.modal_image.show(); self.modal_image.raise_()
        self.start_modal(0.)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self.setGeometry(watched.rect()); self.fit_panel()
            if self.isVisible() and self.modal_motion.state() == QVariantAnimation.Running:
                self.update_modal(self.modal_progress)
        elif hasattr(self, 'scroll') and watched is self.scroll.viewport() and event.type() == QEvent.Resize:
            self.loading.setGeometry(self.scroll.viewport().rect())
            if not self.loading_fonts: QTimer.singleShot(0, self.reflow)
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.backdrop is not None: painter.drawPixmap(self.rect(), self.backdrop)
        painter.fillRect(self.rect(), QColor(0, 0, 0, round(170 * self.modal_progress)))

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()): self.dismiss()
        else: super().mousePressEvent(event)

    def hideEvent(self, event):
        self.modal_motion.stop(); self.grid_motion.stop(); self.nav_motion.stop()
        self.preview_timer.stop(); self.service.preview_queue.clear()
        self.load_generation += 1; self.loading_fonts = False; self.loading.hide()
        self.reveal_generation += 1
        self.modal_image.hide(); self.grid_image.hide()
        if getattr(self, '_restore_preview', False):
            self.parentWidget().preview.show()
            self._restore_preview = False
        for widget in getattr(self, '_disabled_background', []):
            widget.setEnabled(True)
        self._disabled_background = []
        self.backdrop = None
        super().hideEvent(event)

    def open(self, key):
        preview = getattr(self.parentWidget(), 'preview', None)
        if not self.isVisible():
            self.backdrop = self.parentWidget().grab()
            self._disabled_background = [widget for widget in self.parentWidget().findChildren(QWidget, options=Qt.FindDirectChildrenOnly)
                                         if widget is not self and widget.isEnabled()]
            for widget in self._disabled_background: widget.setEnabled(False)
            self._restore_preview = preview is not None and preview.isVisible()
            if self._restore_preview: preview.hide()
        self.closing = False
        self.load_generation += 1
        self.loading_fonts = True
        self.modal_motion.stop()
        self.panel.setEnabled(True)
        for card in self.cards: card.motion.settle()
        self.panel.show()
        self.key = key
        self.title.setText('Font presets · ' + ('Main font' if key == 'font_file' else 'Additional text font'))
        self.setGeometry(self.parentWidget().rect()); self.fit_panel()
        self.loading.setGeometry(self.scroll.viewport().rect()); self.loading.show(); self.loading.raise_()
        self.panel.ensurePolished(); self.panel.layout().activate()
        self.move_indicator()
        self.modal_image.setPixmap(self.panel.grab())
        self.panel.hide(); self.modal_image.show(); self.modal_image.raise_()
        self.show(); self.raise_(); self.setFocus(); self.start_modal(1.)

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
