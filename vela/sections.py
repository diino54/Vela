"""Collapsible settings groups with independent, immediately saved UI state."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QSizePolicy, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QFrame):
    def __init__(self, title, preferences, key):
        super().__init__()
        self.preferences = preferences
        self.settings_key = key
        self.setObjectName("collapsibleSection")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        self.toggle = QToolButton(self)
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setAccessibleName(title + " section")
        self.toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle.setStyleSheet(
            "QToolButton { color: #bdbdbd; font-size: 12px; font-weight: 600; background: transparent; border: none; padding: 2px 0; text-align: left; } QToolButton:hover { color: #ffffff; }"
        )
        outer.addWidget(self.toggle)
        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(12)
        outer.addWidget(self.body)
        expanded = preferences.value(key, True, type=bool)
        self.toggle.setChecked(expanded)
        self.set_expanded(expanded, save=False)
        self.toggle.toggled.connect(self.set_expanded)

    def set_expanded(self, expanded, save=True):
        if self.toggle.isChecked() != expanded:
            self.toggle.blockSignals(True)
            self.toggle.setChecked(expanded)
            self.toggle.blockSignals(False)
        self.body.setVisible(expanded)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.setToolTip("Collapse section" if expanded else "Expand section")
        # Header-only height must not retain the body's layout gap.
        self.layout().setSpacing(12 if expanded else 0)
        if save:
            self.preferences.setValue(self.settings_key, expanded)
            self.preferences.sync()
