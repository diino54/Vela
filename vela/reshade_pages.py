"""ReShade page construction; actions and mutable state stay in the dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from . import reshade
from .controls import NoWheelComboBox, SettingsScroll
from .metric_cards import metric_icon
from .reshade_editor import ReShadeEditor
from .reshade_flow import Page


class ReShadePages:
    """Widget-only builders shared by the ReShade dialog coordinator."""

    def page(self, title, hint):
        scroll = SettingsScroll()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        card = QFrame()
        card.setObjectName("fontCard")
        scroll.setWidget(card)
        content = QVBoxLayout(card)
        content.setContentsMargins(20, 20, 20, 20)
        content.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        content.addWidget(heading)
        if len(self.pages) == Page.READY:
            self.ready_heading = heading
        if len(self.pages) == Page.REVIEW:
            self.review_heading = heading
        label = QLabel(hint)
        label.setWordWrap(True)
        label.setObjectName("fontMeta")
        content.addWidget(label)
        if len(self.pages) == Page.REVIEW:
            self.review_hint = label
        if len(self.pages) == Page.READY:
            self.ready_hint = label
        self.stack.addWidget(scroll)
        self.pages.append(content)
        return content

    def path_row(self, layout, field, callback):
        row = QHBoxLayout()
        row.addWidget(field, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(callback)
        row.addWidget(browse)
        layout.addLayout(row)

    def game_page(self):
        content = self.page(
            "Choose your game",
            "Select the actual Windows game executable, not Steam or a launcher. For Unreal Engine games, look inside Binaries/Win64.",
        )
        content.addWidget(QLabel("Installed Steam games"))
        self.games = NoWheelComboBox()
        self.games.addItem("Browse a game executable manually", None)
        self.games.currentIndexChanged.connect(self.select_game)
        content.addWidget(self.games)
        self.library_status = QLabel("Steam libraries are scanned when this panel opens.")
        self.library_status.setObjectName("fontMeta")
        content.addWidget(self.library_status)
        content.addWidget(QLabel("Game executable"))
        self.executable = QLineEdit()
        self.executable.setPlaceholderText("Select a game executable…")
        self.executable.setAccessibleName("ReShade game executable")
        self.path_row(content, self.executable, self.choose_executable)
        self.executable.textChanged.connect(self.inspect_executable)
        self.detected = QLabel("Choose a game to detect its architecture.")
        self.detected.setWordWrap(True)
        self.detected.setObjectName("fontMeta")
        content.addWidget(self.detected)
        self.api_heading = QLabel("Rendering API")
        content.addWidget(self.api_heading)
        self.api = NoWheelComboBox()
        for label, hook in reshade.APIS.items():
            self.api.addItem(label, hook)
        content.addWidget(self.api)
        self.api_hint = label = QLabel(
            "DirectX games translated by DXVK/VKD3D still use their original DirectX API here. Native Linux games and Windows Vulkan are not supported by this installer."
        )
        label.setWordWrap(True)
        label.setObjectName("fontMeta")
        content.addWidget(label)
        self.remove = QPushButton("Remove Vela installation…")
        self.remove.clicked.connect(self.review_removal)
        self.remove.hide()
        content.addWidget(self.remove, alignment=Qt.AlignLeft)
        content.addStretch()

    def effects_page(self):
        content = self.page(
            "Build your effects library",
            "Install the shader collections you want. Effects stay disabled until you select them in the ReShade in-game menu.",
        )
        self.packages = {}
        for key, (name, description, _) in reshade.PACKAGES.items():
            checkbox = QCheckBox(name)
            checkbox.setChecked(key in ("standard", "sweetfx"))
            content.addWidget(checkbox)
            self.packages[key] = checkbox
            label = QLabel(description)
            label.setObjectName("fontMeta")
            label.setWordWrap(True)
            content.addWidget(label)
        content.addWidget(QLabel("Optional preset (.ini)"))
        self.preset = QLineEdit()
        self.preset.setPlaceholderText("Start clean, or import an existing preset")
        self.path_row(content, self.preset, self.choose_preset)
        label = QLabel(
            "A preset may need additional shaders or textures. Only the selected collections are downloaded; custom dependencies are not installed automatically."
        )
        label.setObjectName("fontMeta")
        label.setWordWrap(True)
        content.addWidget(label)
        content.addSpacing(8)
        appearance_card = QFrame()
        appearance_card.setObjectName("reshadeAppearance")
        appearance_card.setStyleSheet(
            "QFrame#reshadeAppearance { background: #181818; border: 1px solid #353535; border-radius: 9px; }"
        )
        appearance = QVBoxLayout(appearance_card)
        appearance.setContentsMargins(18, 18, 18, 18)
        appearance.setSpacing(14)
        heading = QLabel("Interface & appearance")
        heading.setObjectName("sectionTitle")
        appearance.addWidget(heading)
        self.rounded_ui = QCheckBox("Vela ReShade · rounded UI, blur & animations")
        self.rounded_ui.setChecked(True)
        appearance.addWidget(self.rounded_ui)
        rounded_hint = QLabel(
            "Uses Vela’s modified runtime for whole-window rounding, GPU backdrop blur and UI animations. Disable to download the official runtime."
        )
        rounded_hint.setWordWrap(True)
        rounded_hint.setObjectName("fontMeta")
        appearance.addWidget(rounded_hint)
        self.vela_ui = QCheckBox("Apply Vela UI theme")
        self.vela_ui.setChecked(True)
        appearance.addWidget(self.vela_ui)
        theme_hint = QLabel(
            "Dark charcoal surfaces, white text, blue accents and rounded corners. Global alpha: 0.7. Global and text editor font size: 13 · Show FPS: off · HDR overlay brightness: 400 nits (maximum)."
        )
        theme_hint.setWordWrap(True)
        theme_hint.setObjectName("fontMeta")
        appearance.addWidget(theme_hint)
        content.addWidget(appearance_card)
        content.addStretch()

    def confirmation_option(self, text, name):
        field = QCheckBox(text)
        field.setObjectName(name)
        field.setMinimumHeight(58)
        field.setStyleSheet(
            "QCheckBox { background: #252d39; border: 1px solid #4a6487; border-radius: 8px; padding: 12px; color: #f3f5f8; font-size: 13px; font-weight: 600; spacing: 12px; } QCheckBox:hover { background: #293444; border-color: #6882a5; } QCheckBox::indicator { width: 20px; height: 20px; }"
        )
        return field

    def review_page(self):
        content = self.page(
            "Ready to install",
            "Vela downloads the standard runtime directly from reshade.me and shaders from their authors. Existing mods and configuration files are never overwritten.",
        )
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content.addWidget(self.summary)
        self.complete_removal = self.confirmation_option(
            "Delete everything, including modified presets and shaders", "reshadeRemovalScope"
        )
        self.complete_removal.hide()
        self.complete_removal.toggled.connect(self.update_removal_review)
        content.addWidget(self.complete_removal)
        self.removal_files = QPlainTextEdit()
        self.removal_files.setReadOnly(True)
        self.removal_files.setMaximumHeight(140)
        self.removal_files.setStyleSheet(
            "QPlainTextEdit { background: #111; color: #aaa; border: 1px solid #303030; border-radius: 7px; padding: 8px; }"
        )
        self.removal_files.hide()
        content.addWidget(self.removal_files)
        self.confirm = self.confirmation_option(
            "The game is closed and this is the correct executable.", "reshadeConfirm"
        )
        content.addWidget(self.confirm)
        self.review_tiles = QVBoxLayout()
        self.review_tiles.setContentsMargins(0, 0, 0, 0)
        content.insertLayout(3, self.review_tiles)
        content.addStretch()

    def install_page(self):
        content = self.page(
            "Installing ReShade",
            "Keep Vela open while the runtime and shader files are installed. Closing this panel returns the wizard to step 1; an active operation finishes in the background.",
        )
        self.install_progress = QProgressBar()
        self.install_progress.setRange(0, 0)
        self.install_progress.setFixedHeight(6)
        self.install_progress.setTextVisible(False)
        content.addWidget(self.install_progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(150)
        self.log.setStyleSheet(
            "QPlainTextEdit { background: #111; border: 1px solid #303030; border-radius: 7px; padding: 12px; color: #aaa; }"
        )
        content.addWidget(self.log, 1)

    def ready_page(self):
        content = self.page(
            "ReShade is installed",
            "Paste these launch options into Steam → Properties → Launch Options. Vela does not change Steam settings automatically.",
        )
        self.command = QPlainTextEdit()
        self.command.setReadOnly(True)
        self.command.setFixedHeight(88)
        self.command.setStyleSheet(
            "QPlainTextEdit { background: #111111; color: #dddddd; border: 1px solid #303030; border-radius: 7px; padding: 12px; selection-background-color: #246bce; }"
        )
        content.addWidget(self.command)
        row = QHBoxLayout()
        self.copy_launch = copy = QPushButton("Copy launch options")
        copy.clicked.connect(self.copy_command)
        row.addWidget(copy)
        self.game_directory = directory = QPushButton("Open game directory")
        directory.clicked.connect(self.open_directory)
        row.addWidget(directory)
        row.addStretch()
        content.addLayout(row)
        self.ready_detail = QLabel(
            "Start the game and press Home to open ReShade. The first shader compilation can take a moment. Choose effects in-game; MangoHud settings remain independent."
        )
        self.ready_detail.setWordWrap(True)
        content.addWidget(self.ready_detail)
        self.another_game = another = QPushButton("Set up another game")
        another.clicked.connect(lambda: self.go(Page.HOME))
        content.addWidget(another, alignment=Qt.AlignLeft)
        content.addStretch()

    def entry_pages(self):
        content = self.page(
            "ReShade", "Install ReShade for a game, or manage an existing installation."
        )
        row = QHBoxLayout()
        row.setSpacing(16)
        for mode, title, description, icon in (
            ("configure", "Configure", "Manage an existing installation", "session"),
            ("install", "Install", "Set up ReShade for a game", "monitor"),
        ):
            button = QPushButton()
            button.setAccessibleName(title)
            button.setAccessibleDescription(description)
            button.setMinimumHeight(170)
            button.setStyleSheet(
                "QPushButton { min-height: 170px; background: #202020; border: 1px solid #383838; border-radius: 9px; padding: 0; } QPushButton:hover { background: #292d34; border-color: #6483aa; } QPushButton:focus { border-color: #83a8dc; }"
            )
            tile = QVBoxLayout(button)
            tile.setContentsMargins(20, 20, 20, 20)
            tile.setSpacing(10)
            symbol = QLabel()
            symbol.setPixmap(metric_icon(icon))
            symbol.setAlignment(Qt.AlignCenter)
            caption = QLabel(title)
            caption.setAlignment(Qt.AlignCenter)
            caption.setStyleSheet(
                "color: #f2f2f2; font-size: 16px; font-weight: 600; background: transparent;"
            )
            detail = QLabel(description)
            detail.setAlignment(Qt.AlignCenter)
            detail.setWordWrap(True)
            detail.setStyleSheet("color: #a5a5a5; font-size: 12px; background: transparent;")
            tile.addStretch()
            tile.addWidget(symbol)
            tile.addWidget(caption)
            tile.addWidget(detail)
            tile.addStretch()
            for label in (symbol, caption, detail):
                label.setAttribute(Qt.WA_TransparentForMouseEvents)
            button.clicked.connect(lambda _=False, choice=mode: self.choose_mode(choice))
            setattr(self, mode + "_choice", button)
            row.addWidget(button, 1)
        content.addLayout(row)
        content.addStretch()
        content = self.page("Configure ReShade", "Manage ReShade files for the selected game.")
        self.game_card = QFrame()
        self.game_card.setObjectName("reshadeGameCard")
        self.game_card.setStyleSheet(
            "QFrame#reshadeGameCard { background: #202f45; border: 1px solid #426da5; border-radius: 9px; }"
        )
        game = QHBoxLayout(self.game_card)
        game.setContentsMargins(16, 16, 16, 16)
        game.setSpacing(12)
        symbol = QLabel()
        symbol.setPixmap(metric_icon("game"))
        game.addWidget(symbol, alignment=Qt.AlignTop)
        details = QVBoxLayout()
        details.setSpacing(6)
        self.game_title = QLabel()
        self.game_title.setTextFormat(Qt.PlainText)
        self.game_title.setWordWrap(True)
        self.game_title.setStyleSheet("color: #f4f7fc; font-size: 16px; font-weight: 600;")
        details.addWidget(self.game_title)
        self.configure_info = QLabel()
        self.configure_info.setWordWrap(True)
        self.configure_info.setStyleSheet("color: #b4c5dd; font-size: 11px;")
        self.configure_info.setTextFormat(Qt.PlainText)
        details.addWidget(self.configure_info)
        game.addLayout(details, 1)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        directory = QPushButton()
        directory.setIcon(QIcon(metric_icon("folder")))
        directory.setFixedSize(34, 34)
        directory.setToolTip("Open game directory")
        directory.setAccessibleName("Open game directory")
        directory.clicked.connect(self.open_directory)
        actions.addWidget(directory)
        self.open_ini = QPushButton()
        self.open_ini.setIcon(QIcon(metric_icon("edit")))
        self.open_ini.setFixedSize(34, 34)
        self.open_ini.setToolTip("Open ReShade.ini")
        self.open_ini.setAccessibleName("Open ReShade.ini")
        self.open_ini.clicked.connect(self.open_configuration)
        actions.addWidget(self.open_ini)
        self.remove.setText("")
        self.remove.setIcon(QIcon(metric_icon("trash")))
        self.remove.setFixedSize(34, 34)
        self.remove.setToolTip("Remove Vela ReShade installation")
        self.remove.setAccessibleName("Remove Vela ReShade installation")
        actions.addWidget(self.remove)
        for button in (directory, self.open_ini, self.remove):
            button.setStyleSheet(
                "QPushButton { background: #2b405d; border: 1px solid #4c6384; border-radius: 6px; } QPushButton:hover { background: #375273; border-color: #7299ca; }"
            )
        game.addLayout(actions)
        content.addWidget(self.game_card)
        self.editor = ReShadeEditor()
        self.editor.dirtyChanged.connect(self.sync_action)
        content.addWidget(self.editor)
        self.editor_status = QLabel()
        self.editor_status.setWordWrap(True)
        self.editor_status.setObjectName("fontMeta")
        content.addWidget(self.editor_status)
        content.addStretch()
