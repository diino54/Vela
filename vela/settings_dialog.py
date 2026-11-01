"""Application settings modal; retains Window's configuration action handlers."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from . import mangohud
from .controls import PathEdit
from .modal import FrostedModal


class SettingsDialog(FrostedModal):
    def __init__(self, owner):
        super().__init__(owner)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("panelTitle")
        header.addWidget(title, 1)
        close = QPushButton("Close  ×")
        close.clicked.connect(self.dismiss)
        header.addWidget(close)
        layout.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(18)
        layout.addLayout(body, 1)
        sidebar = QFrame()
        sidebar.setObjectName("fontSidebar")
        sidebar.setFixedWidth(148)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(10, 16, 10, 16)
        nav.setSpacing(5)
        label = QLabel("SETTINGS")
        label.setObjectName("fontMeta")
        nav.addWidget(label)
        nav.addSpacing(10)
        selected = QPushButton("Configuration")
        selected.setAccessibleName("Configuration settings")
        selected.setStyleSheet(
            "QPushButton { background: #353535; border: none; text-align: left; padding: 0 12px; min-height: 36px; }"
        )
        nav.addWidget(selected)
        nav.addStretch()
        body.addWidget(sidebar)
        card = QFrame()
        card.setObjectName("fontCard")
        content = QVBoxLayout(card)
        content.setContentsMargins(20, 20, 20, 20)
        content.setSpacing(14)
        heading = QLabel("MangoHud configuration")
        heading.setObjectName("panelTitle")
        content.addWidget(heading)
        hint = QLabel(
            "Choose the global configuration used by Vela and inspect its contents. Appearance changes are saved with Save configuration in the main window."
        )
        hint.setWordWrap(True)
        hint.setObjectName("fontMeta")
        content.addWidget(hint)
        owner.config_path = PathEdit(
            str(owner.preferences.value("global_config", str(mangohud.default_config())))
        )
        owner.config_path.setAccessibleName("Global MangoHud configuration")
        owner.config_path.setToolTip(
            "Preview inherits this file; changing this path loads it into the preview."
        )
        content.addWidget(QLabel("Global MangoHud file"))
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(owner.config_path, 1)
        owner.browse_config = QPushButton("Browse…")
        owner.browse_config.setAccessibleName("Choose MangoHud configuration")
        row.addWidget(owner.browse_config)
        content.addLayout(row)
        owner.open_config_directory = QPushButton("Open directory")
        owner.open_config_directory.setIcon(
            QIcon.fromTheme("folder-open", owner.style().standardIcon(QStyle.SP_DirOpenIcon))
        )
        owner.open_config_directory.clicked.connect(owner.open_configuration_directory)
        content.addWidget(owner.open_config_directory, alignment=Qt.AlignLeft)
        content.addWidget(QLabel("File contents"))
        owner.config_contents = QPlainTextEdit()
        owner.config_contents.setReadOnly(True)
        owner.config_contents.setAccessibleName("Global configuration contents")
        owner.config_contents.setMinimumHeight(180)
        owner.config_contents.setStyleSheet(
            "QPlainTextEdit { background: #111111; color: #aaaaaa; border: 1px solid #2c2c2c; border-radius: 5px; padding: 8px; font-family: monospace; font-size: 11px; }"
        )
        content.addWidget(owner.config_contents, 1)
        body.addWidget(card, 1)
        owner.config_path.editingFinished.connect(owner.change_global_config)
        owner.browse_config.clicked.connect(owner.choose_global_config)

    def fit_panel(self):
        """Use the same compact, centered bounds as the ReShade wizard."""
        self.setGeometry(self.parentWidget().rect())
        width = min(900, max(0, self.width() - 48))
        height = min(680, max(0, self.height() - 48))
        self.panel.setGeometry(
            (self.width() - width) // 2, (self.height() - height) // 2, width, height
        )
        self.target_rect = self.panel.geometry()

    def open(self):
        self.parentWidget().update_config_contents()
        super().open()
