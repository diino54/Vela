"""Editable ReShade metric cards; changes remain local until Save changes."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import reshade_config
from .controls import NoWheelComboBox, NoWheelSpinBox, NumberControl
from .metric_cards import metric_icon


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class ReShadeEditor(QWidget):
    dirtyChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loaded = False
        self.loading = False
        self.path = None
        self.baseline = {}
        self.controls = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search ReShade settings")
        outer.addWidget(self.search)
        self.empty = QLabel("No matching settings.")
        self.empty.setObjectName("fontMeta")
        self.empty.hide()
        outer.addWidget(self.empty)
        grid = self.grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        outer.addLayout(grid)
        self.cards = []
        self.toggles = {}
        self.theme = NoWheelComboBox()
        for title, value in (
            ("Keep current theme", "current"),
            ("Vela", "vela"),
            ("Default", "default"),
        ):
            self.theme.addItem(title, value)
        self.blur_quality = NoWheelComboBox()
        for title, value in (
            ("Low · 9 samples", 0),
            ("Balanced · 25 samples", 1),
            ("High · 49 samples", 2),
        ):
            self.blur_quality.addItem(title, value)
        self.blur_quality.currentIndexChanged.connect(self.changed)
        entries = [
            ("theme", "UI Theme", "color", self.theme),
            ("blur_quality", "Vela · Blur Quality", "scale", self.blur_quality),
        ]
        for name, title, icon in (
            ("alpha", "Global Alpha", "sun"),
            ("blur", "Vela · Background Blur", "monitor"),
            ("animation_duration", "Vela · Animation Duration", "refresh"),
            ("font", "Global Font Size", "session"),
            ("editor_font", "Editor Font Size", "session"),
            ("rounding", "Corner Rounding", "scale"),
            ("hdr", "HDR Overlay Brightness", "sun"),
            ("font_scale", "Global Font Scale", "scale"),
            ("fps_scale", "FPS Counter Scale", "scale"),
            ("child_rounding", "Child Window Rounding", "scale"),
            ("popup_rounding", "Popup Rounding", "scale"),
            ("frame_rounding", "Control Rounding", "scale"),
            ("grab_rounding", "Slider Handle Rounding", "scale"),
            ("scrollbar_rounding", "Scrollbar Rounding", "scale"),
            ("tab_rounding", "Tab Rounding", "scale"),
        ):
            field = NoWheelSpinBox()
            field.setAccessibleName(title)
            field.setButtonSymbols(QAbstractSpinBox.NoButtons)
            section, key, default, low, high = reshade_config.FIELDS[name]
            field.setRange(low, high)
            field.setDecimals(
                2
                if name in ("alpha", "font_scale", "fps_scale", "animation_duration")
                else 0
                if name == "hdr"
                else 1
            )
            field.setSingleStep(
                0.05
                if name in ("alpha", "font_scale", "fps_scale", "animation_duration")
                else 1
                if name != "hdr"
                else 10
            )
            if name == "animation_duration":
                field.setSuffix(" s")
                field.setSingleStep(0.02)
            if name == "blur":
                field.setSuffix(" px")
            if name == "hdr":
                field.setSuffix(" nits")
            self.controls[name] = field
            entries.append((name, title, icon, NumberControl(field)))
            field.valueChanged.connect(self.changed)
        for name, title in (
            ("fps", "Overlay FPS Counter"),
            ("animations", "Vela · UI Animations"),
            ("clock", "Clock"),
            ("frametime", "Frame Time"),
            ("preset_name", "Preset Name"),
            ("screenshot_message", "Screenshot Notifications"),
            ("auto_save_preset", "Auto-save Preset"),
            ("variable_tabs", "Effect Variable Tabs"),
        ):
            field = QCheckBox("Enabled")
            field.setAccessibleName(title)
            self.toggles[name] = field
            field.toggled.connect(self.changed)
            entries.append((name, title, "monitor", field))
        self.fps = self.toggles["fps"]
        for index, (name, title, icon, control) in enumerate(entries):
            card = QFrame()
            card.setObjectName("fontCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)
            symbol = QLabel()
            symbol.setPixmap(metric_icon(icon))
            layout.addWidget(symbol)
            label = QLabel(title)
            label.setObjectName("fontMeta")
            layout.addWidget(label)
            layout.addWidget(control)
            if name == "alpha":
                self.alpha_slider = NoWheelSlider(Qt.Horizontal)
                self.alpha_slider.setRange(10, 100)
                self.alpha_slider.setAccessibleName("Global alpha slider")
                self.alpha_slider.valueChanged.connect(
                    lambda value: self.controls["alpha"].setValue(value / 100)
                )
                self.controls["alpha"].valueChanged.connect(self.sync_alpha_slider)
                layout.addWidget(self.alpha_slider)
            grid.addWidget(card, index // 2, index % 2)
            self.cards.append((card, (title + " " + name).casefold()))
        for column in (0, 1):
            grid.setColumnStretch(column, 1)
        self.theme.currentIndexChanged.connect(self.changed)
        self.search.textChanged.connect(self.filter_cards)

    def filter_cards(self, query):
        words = query.casefold().split()
        while self.grid.count():
            self.grid.takeAt(0)
        visible = 0
        for card, keywords in self.cards:
            match = all(word in keywords for word in words)
            card.setVisible(match)
            if match:
                self.grid.addWidget(card, visible // 2, visible % 2)
                visible += 1
        self.empty.setVisible(not visible)

    def sync_alpha_slider(self, value):
        with QSignalBlocker(self.alpha_slider):
            self.alpha_slider.setValue(round(value * 100))

    def values(self):
        return dict(
            theme=self.theme.currentData(),
            blur_quality=self.blur_quality.currentData(),
            **{name: field.isChecked() for name, field in self.toggles.items()},
            **{name: field.value() for name, field in self.controls.items()},
        )

    def dirty(self):
        return self.loaded and self.values() != self.baseline

    def changed(self, *_):
        if not self.loading:
            self.dirtyChanged.emit()

    def load(self, path):
        self.loaded = False
        self.path = path
        self.search.clear()
        raw, values = reshade_config.load(path)
        self.loading = True
        try:
            self.original = raw
            self.theme.model().item(0).setEnabled(values["theme"] == "current")
            self.theme.setCurrentIndex(self.theme.findData(values["theme"]))
            self.blur_quality.setCurrentIndex(
                self.blur_quality.findData(int(values["blur_quality"]))
            )
            for name, field in self.toggles.items():
                field.setChecked(values[name])
            for name, field in self.controls.items():
                low, high = reshade_config.FIELDS[name][3:]
                field.setRange(min(low, values[name]), max(high, values[name]))
                field.setValue(values[name])
            self.baseline = self.values()
            self.loaded = True
        finally:
            self.loading = False
        self.setEnabled(True)
        self.dirtyChanged.emit()

    def save(self):
        query = self.search.text()
        reshade_config.save(self.path, self.original, self.values(), self.baseline)
        self.load(self.path)
        self.search.setText(query)
