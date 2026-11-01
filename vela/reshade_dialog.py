"""Animated ReShade wizard. Workers own I/O; widgets stay on the Qt thread."""

import configparser
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from . import reshade
from .animation import ButtonGlow, FieldGlow
from .metric_cards import MetricGrid
from .modal import FrostedModal
from .reshade_flow import Page, panel_size
from .reshade_pages import ReShadePages
from .reshade_workers import InstallWorker, LibraryWorker


class ReShadeDialog(ReShadePages, FrostedModal):
    STEPS = ("Game", "Effects", "Review", "Install", "Ready")

    def __init__(self, owner):
        super().__init__(owner)
        self.worker = None
        self.library_worker = None
        self.library_scan_failed = False
        self.step = Page.GAME
        self.operation_active = False
        self.reset_after_close = False
        self.ready_removed = False
        self.installed = False
        self.removing = False
        self.plan = None
        self.mode = None
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel("ReShade")
        title.setObjectName("panelTitle")
        header.addWidget(title, 1)
        subtitle = QLabel("Post-processing for Proton & Wine")
        subtitle.setObjectName("fontMeta")
        header.addWidget(subtitle)
        self.close_button = QPushButton("Close  ×")
        self.close_button.clicked.connect(self.dismiss)
        header.addWidget(self.close_button)
        layout.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(18)
        layout.addLayout(body, 1)
        sidebar = self.sidebar = QFrame()
        sidebar.setObjectName("fontSidebar")
        sidebar.setFixedWidth(148)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(10, 16, 10, 16)
        nav.setSpacing(8)
        label = QLabel("INSTALLATION")
        label.setObjectName("fontMeta")
        nav.addWidget(label)
        nav.addSpacing(12)
        self.step_labels = []
        for index, text in enumerate(self.STEPS):
            label = QLabel(f"{index + 1:02}   {text}")
            label.setMinimumHeight(36)
            nav.addWidget(label)
            self.step_labels.append(label)
        nav.addStretch()
        source = QPushButton("ReShade website ↗")
        source.setObjectName("fontSource")
        source.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(reshade.HOME)))
        nav.addWidget(source)
        body.addWidget(sidebar)
        right = QVBoxLayout()
        right.setSpacing(12)
        body.addLayout(right, 1)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        self.pages = []
        self.game_page()
        self.effects_page()
        self.review_page()
        self.install_page()
        self.ready_page()
        self.entry_pages()
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #e3a283;")
        self.error.hide()
        right.addWidget(self.error)
        footer = QHBoxLayout()
        self.back = QPushButton("Back")
        self.back.clicked.connect(self.go_back)
        footer.addWidget(self.back)
        footer.addStretch()
        self.next = QPushButton("Continue")
        self.next.setObjectName("apply")
        self.next.setMinimumWidth(150)
        self.next.clicked.connect(self.advance)
        footer.addWidget(self.next)
        right.addLayout(footer)
        self.next_glow = ButtonGlow(self.next)
        self.next_glow.set_active(True)
        self.fade = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.fade)
        self.page_fade = QPropertyAnimation(self.fade, b"opacity", self)
        self.page_fade.setDuration(280)
        self.page_fade.setEasingCurve(QEasingCurve.OutCubic)
        self.page_fade.finished.connect(lambda: self.fade.setEnabled(False))
        self.validation_glows = {}
        self.validation_styles = {}
        self.executable.textChanged.connect(lambda: self.clear_invalid(self.executable))
        self.preset.textChanged.connect(lambda: self.clear_invalid(self.preset))
        self.confirm.toggled.connect(lambda: self.clear_invalid(self.confirm))
        self.executable.textChanged.connect(lambda: self.clear_invalid(self.remove))
        self.executable.textChanged.connect(self.sync_action)
        self.preset.textChanged.connect(self.sync_action)
        self.confirm.toggled.connect(self.sync_action)
        self.go(Page.HOME, animate=False)

    def fit_panel(self):
        """Keep this form-sized wizard centered independently of other modals."""
        self.setGeometry(self.parentWidget().rect())
        max_width, max_height = panel_size(self.step, self.mode, self.ready_removed)
        width = min(max_width, max(0, self.width() - 48))
        height = min(max_height, max(0, self.height() - 48))
        self.panel.setGeometry(
            (self.width() - width) // 2, (self.height() - height) // 2, width, height
        )
        self.target_rect = self.panel.geometry()

    def choose_mode(self, mode):
        if self.operation_active:
            return
        self.mode = mode
        self.go(Page.GAME)

    def go_back(self):
        if self.removing:
            target = Page.CONFIGURE
        elif self.step in (Page.GAME, Page.CONFIGURE):
            target = Page.HOME
        else:
            target = Page(self.step - 1)
        self.go(target)

    def configure_target(self):
        if self.operation_active:
            return
        plan = self.make_plan()
        try:
            executable = plan.executable.resolve(strict=True)
            reshade.pe_bits(executable)
            folder = executable.parent
            names = {path.name.casefold() for path in folder.iterdir()}
        except (OSError, ValueError) as error:
            self.mark_invalid(self.executable, str(error), Page.GAME)
            return
        self.mode = "configure"
        self.plan = plan
        installed = bool(names.intersection({*reshade.HOOKS, "reshade.ini", reshade.JOURNAL}))
        managed = (folder / reshade.JOURNAL).is_file()
        game_name = self.plan.executable.stem
        for index in range(1, self.games.count()):
            library_path = Path(self.games.itemData(index)).resolve()
            if library_path == folder or library_path in folder.parents:
                game_name = self.games.itemText(index)
                break
        self.game_title.setText(game_name)
        self.configure_info.setText(
            f"{folder}\n"
            + (
                "Vela-managed ReShade installation detected."
                if managed
                else "Existing ReShade or graphics hook detected. Automatic removal is available only for Vela-managed installations."
                if installed
                else "No ReShade installation found for this executable."
            )
        )
        self.remove.setVisible(managed)
        self.open_ini.setEnabled((folder / "ReShade.ini").is_file())
        self.editor.loaded = False
        try:
            self.editor.load(folder / "ReShade.ini")
            self.editor.show()
            self.editor_status.setText(
                "Edit values, then Save changes. Restart the game to apply them. Whole-window rounding requires the Vela runtime; blur and animations require Vela ReShade 6.8.0.4+."
            )
        except (OSError, ValueError, configparser.Error) as error:
            self.editor.hide()
            self.editor_status.setText("Settings unavailable: " + str(error))
        self.go(Page.CONFIGURE)

    def open_configuration(self):
        if self.plan:
            path = self.plan.executable.resolve().parent / "ReShade.ini"
            if path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open(self):
        if not self.isVisible() or self.closing:
            self.reset_defaults()
        super().open()
        if self.library_worker is None:
            self.library_scan_failed = False
            self.library_worker = LibraryWorker(self)
            self.library_worker.result.connect(self.libraries_loaded, Qt.QueuedConnection)
            self.library_worker.failed.connect(self.library_failed, Qt.QueuedConnection)
            self.library_worker.finished.connect(self.library_finished, Qt.QueuedConnection)
            self.library_worker.start()

    def dismiss(self):
        if self.isVisible() and not self.closing:
            self.reset_after_close = True
        super().dismiss()
        if self.closing:
            self.reset_defaults()

    def reset_defaults(self):
        """Reset the form only; an active worker owns its immutable plan."""
        for field in self.validation_glows:
            self.clear_invalid(field)
        self.removing = False
        self.mode = None
        self.plan = None
        self.editor.loaded = False
        self.ready_removed = False
        self.installed = False
        while self.review_tiles.count():
            item = self.review_tiles.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.games.blockSignals(True)
        self.games.setCurrentIndex(0)
        self.games.blockSignals(False)
        self.executable.clear()
        self.api.setCurrentIndex(0)
        self.preset.clear()
        for key, box in self.packages.items():
            box.setChecked(key in ("standard", "sweetfx"))
        self.rounded_ui.setEnabled(True)
        self.rounded_ui.setChecked(True)
        self.rounded_ui.setToolTip("")
        self.vela_ui.setChecked(True)
        self.confirm.setChecked(False)
        self.complete_removal.setChecked(False)
        for field in (self.summary, self.removal_files, self.command, self.log, self.error):
            field.clear()
        self.remove.hide()
        self.detected.setText("Select a valid x86 or x64 Windows executable.")
        self.install_progress.setRange(0, 1)
        self.install_progress.setValue(0)
        for index in range(self.stack.count()):
            self.stack.widget(index).verticalScrollBar().setValue(0)
        self.go(Page.HOME, animate=False)

    @Slot(object)
    def libraries_loaded(self, games):
        for name, path in games:
            self.games.addItem(name, str(path))
        self.library_status.setText(
            f"{len(games)} installed Steam games found. Choose one to browse its executable."
        )

    @Slot(str)
    def library_failed(self, message):
        self.library_status.setText("Steam library scan failed. Browse an executable manually.")
        self.library_status.setToolTip(message)
        self.library_scan_failed = True

    @Slot()
    def library_finished(self):
        if self.library_scan_failed:
            self.library_worker.deleteLater()
            self.library_worker = None

    def select_game(self):
        path = self.games.currentData()
        if path:
            self.choose_executable(directory=path)

    def choose_executable(self, _checked=False, directory=None):
        initial = directory or (
            str(Path(self.executable.text()).parent) if self.executable.text() else str(Path.home())
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose game executable", initial, "Windows executables (*.exe *.EXE)"
        )
        if path:
            self.executable.setText(path)

    def choose_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import ReShade preset", str(Path.home()), "ReShade presets (*.ini)"
        )
        if path:
            self.preset.setText(path)

    def inspect_executable(self):
        self.detected.setToolTip("")
        try:
            path = Path(self.executable.text()).expanduser()
            bits = reshade.pe_bits(path)
            self.detected.setText(f"{bits}-bit Windows executable · {path.name}")
            available = reshade.rounded_available(bits)
            self.rounded_ui.setEnabled(available)
            self.rounded_ui.setToolTip(
                "Rounded whole-window rendering with the Vela build."
                if available
                else "The Vela rounded runtime is not installed for this architecture."
            )
            if not available:
                self.rounded_ui.setChecked(False)
            self.remove.setVisible((path.parent / reshade.JOURNAL).is_file())
            names = {item.name.casefold() for item in path.parent.iterdir()}
            existing = names.intersection({*reshade.HOOKS, "reshade.ini", reshade.JOURNAL})
            if (
                existing
                and self.step == Page.GAME
                and self.mode == "install"
                and self.isVisible()
                and not self.closing
            ):
                selected = self.executable.text()
                QTimer.singleShot(
                    0,
                    lambda: (
                        self.configure_target()
                        if self.step == Page.GAME
                        and self.mode == "install"
                        and self.executable.text() == selected
                        and not self.closing
                        else None
                    ),
                )
        except (OSError, ValueError):
            self.detected.setText("Select a valid x86 or x64 Windows executable.")
            self.remove.hide()

    def make_plan(self):
        return reshade.Plan(
            Path(self.executable.text()).expanduser(),
            self.api.currentData(),
            tuple(key for key, box in self.packages.items() if box.isChecked()),
            Path(self.preset.text()).expanduser() if self.preset.text().strip() else None,
            self.vela_ui.isChecked(),
            self.rounded_ui.isChecked(),
        )

    def go(self, step, animate=True):
        step = Page(step)
        self.page_fade.stop()
        self.fade.setEnabled(False)
        self.step = step
        self.stack.setCurrentIndex(step)
        self.error.hide()
        self.sidebar.setVisible(
            step not in (Page.HOME, Page.CONFIGURE) and self.mode != "configure"
        )
        for widget in (self.api_heading, self.api, self.api_hint):
            widget.setVisible(self.mode != "configure")
        if step != Page.REVIEW:
            self.removing = False
        if step in (Page.GAME, Page.EFFECTS):
            self.removing = False
            self.complete_removal.hide()
            self.removal_files.hide()
        for index, label in enumerate(self.step_labels):
            label.setStyleSheet(
                "color: "
                + ("#eee; background: #333; border-radius: 6px;" if index == step else "#929292;")
                + " padding: 0 10px;"
            )
        removal_done = step == Page.READY and self.ready_removed
        self.close_button.setVisible(not removal_done)
        self.another_game.setVisible(not removal_done)
        self.back.setVisible(step in (Page.GAME, Page.EFFECTS, Page.REVIEW, Page.CONFIGURE))
        self.next.setVisible(
            step not in (Page.INSTALL, Page.HOME) and (step != Page.CONFIGURE or self.editor.loaded)
        )
        self.next.setText(
            "Save changes"
            if step == Page.CONFIGURE
            else "Install ReShade"
            if step == Page.REVIEW
            else "Done"
            if step == Page.READY
            else "Continue"
        )
        self.next.setEnabled(not self.operation_active)
        self.install_choice.setEnabled(not self.operation_active)
        self.configure_choice.setEnabled(not self.operation_active)
        self.sync_action()
        if not self.closing:
            self.fit_panel()
        if animate:
            self.fade.setEnabled(True)
            self.page_fade.setStartValue(0.15)
            self.page_fade.setEndValue(1.0)
            self.page_fade.start()
        else:
            self.fade.setOpacity(1.0)

    def sync_action(self, *_):
        """A soft visual hint only: clicking still validates missing choices."""
        ready = True
        if self.step in (Page.GAME, Page.EFFECTS):
            try:
                target = Path(self.executable.text()).expanduser()
                ready = target.suffix.lower() == ".exe" and bool(reshade.pe_bits(target))
                if self.step == Page.EFFECTS and self.preset.text().strip():
                    preset = Path(self.preset.text()).expanduser()
                    ready = (
                        ready
                        and preset.suffix.lower() == ".ini"
                        and preset.is_file()
                        and preset.stat().st_size <= 4 * 1024 * 1024
                    )
            except (OSError, ValueError):
                ready = False
        elif self.step == Page.REVIEW:
            ready = self.confirm.isChecked()
        elif self.step == Page.CONFIGURE:
            ready = self.editor.dirty()
            self.next.setEnabled(ready and not self.operation_active)
        self.next.setProperty("awaitingChoice", not ready)
        self.next.setStyleSheet(
            ""
            if ready
            else "QPushButton#apply { background: #24528e; color: #b9c5d8; border: 1px solid #38649c; } "
            "QPushButton#apply:hover { background: #2b609f; color: #e5ecf5; }"
        )
        self.next_glow.set_active(ready and not self.operation_active)

    def clear_invalid(self, field):
        glow = self.validation_glows.get(field)
        if glow:
            glow.set_active(False)
            field.setStyleSheet(self.validation_styles[field])
            field.setToolTip("")
            field.setAccessibleDescription("")

    def mark_invalid(self, field, message, step):
        if self.step != step:
            self.go(step)
        if field not in self.validation_glows:
            self.validation_styles[field] = field.styleSheet()
            self.validation_glows[field] = FieldGlow(field)
        field.setToolTip(message)
        field.setAccessibleDescription(message)
        self.validation_glows[field].set_active(True)
        field.setFocus()
        self.stack.currentWidget().ensureWidgetVisible(field)
        # Responsive review cards may reflow after this event; reveal the
        # confirmation again once the scroll area's layout has settled.
        QTimer.singleShot(
            150,
            lambda: (
                self.stack.currentWidget().ensureWidgetVisible(field, 20, 20)
                if self.step == step and field.isVisible() and self.validation_glows[field].active
                else None
            ),
        )

    def validate_form(self):
        self.plan = self.make_plan()
        if self.plan.preset:
            preset = self.plan.preset
            try:
                valid = (
                    preset.suffix.lower() == ".ini"
                    and preset.is_file()
                    and preset.stat().st_size <= 4 * 1024 * 1024
                )
            except OSError:
                valid = False
            if not valid:
                self.mark_invalid(
                    self.preset, "Choose a valid ReShade preset .ini (up to 4 MiB).", 1
                )
                return None
        try:
            result = reshade.validate(self.plan)
            self.clear_invalid(self.executable)
            self.clear_invalid(self.preset)
            self.clear_invalid(self.remove)
            return result
        except reshade.ExistingInstallationError:
            self.clear_invalid(self.executable)
            self.configure_target()
            return None
        except (OSError, ValueError) as error:
            self.mark_invalid(self.executable, str(error), Page.GAME)
            return None

    def render_review(self, metrics):
        while self.review_tiles.count():
            item = self.review_tiles.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.review_tiles.addWidget(MetricGrid(metrics))
        self.summary.hide()

    def advance(self):
        if self.operation_active:
            return
        try:
            if self.step == Page.GAME and self.mode == "configure":
                try:
                    reshade.pe_bits(Path(self.executable.text()).expanduser())
                except (OSError, ValueError) as error:
                    self.mark_invalid(self.executable, str(error), Page.GAME)
                    return
                self.configure_target()
                return
            if self.step in (Page.GAME, Page.EFFECTS):
                validated = self.validate_form()
                if validated is None:
                    return
                exe, bits = validated
                if self.step == Page.EFFECTS:
                    self.review_heading.setText("Ready to install")
                    self.review_hint.setText(
                        "Review the selected runtime, effects and Steam launch options. Existing files will not be overwritten."
                    )
                    names = (
                        ", ".join(reshade.PACKAGES[key][0] for key in self.plan.packages)
                        or "Runtime only"
                    )
                    self.render_review(
                        [
                            ("Game", exe.name, "monitor"),
                            ("Architecture", f"{bits}-bit", "gpu"),
                            ("Rendering API", self.api.currentText(), "monitor"),
                            ("Effects", names, "color"),
                            (
                                "Runtime",
                                "Vela ReShade 6.8.0 · rounded"
                                if self.plan.rounded_ui
                                else "Official ReShade · latest",
                                "session",
                            ),
                            (
                                "UI Theme",
                                "Vela · fonts 13 · HDR 400 nits"
                                if self.plan.vela_ui
                                else "ReShade default",
                                "color",
                            ),
                            (
                                "Preset",
                                self.plan.preset.name if self.plan.preset else "Empty preset",
                                "session",
                            ),
                            ("Location", str(exe.parent), "session"),
                        ]
                    )
                    self.confirm.setChecked(False)
                self.go(self.step + 1)
            elif self.step == Page.REVIEW:
                if not self.confirm.isChecked():
                    self.mark_invalid(
                        self.confirm, "Confirm the game is closed and the executable is correct.", 2
                    )
                    return
                self.plan = self.make_plan()
                if self.removing:
                    self.start_job(True)
                    return
                if self.validate_form() is None:
                    return
                self.final_command = reshade.launch_options(self.plan.hook)
                self.start_job(False)
            elif self.step == Page.CONFIGURE:
                if self.editor.dirty():
                    try:
                        self.editor.save()
                        self.editor_status.setText("Changes saved. Restart the game to apply them.")
                    except (OSError, ValueError, configparser.Error) as error:
                        self.show_error(str(error))
            elif self.step == Page.READY:
                self.dismiss()
        except (OSError, ValueError) as error:
            self.show_error(str(error))

    def show_error(self, message):
        self.error.setText(message)
        self.error.show()

    def review_removal(self):
        if self.operation_active:
            return
        self.clear_invalid(self.remove)
        # Explicit second click in a dedicated review step, never remove on Browse.
        self.plan = self.make_plan()
        self.go(Page.REVIEW)
        self.review_heading.setText("Remove ReShade")
        self.review_hint.setText(
            "Only unchanged files recorded by Vela are removed. Edited files and other mods are preserved."
        )
        while self.review_tiles.count():
            item = self.review_tiles.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.summary.show()
        self.summary.setText(
            "Remove the Vela ReShade installation from:\n"
            + str(self.plan.executable.parent)
            + "\n\nModified presets, configurations and other changed files will be preserved. Remove the ReShade DLL override from Steam launch options afterwards."
        )
        self.confirm.setChecked(False)
        self.next.setText("Remove ReShade")
        self.removing = True
        self.complete_removal.setChecked(False)
        self.complete_removal.show()
        self.update_removal_review()

    def update_removal_review(self):
        if not self.removing:
            return
        self.confirm.setChecked(False)
        complete = self.complete_removal.isChecked()
        self.next.setText("Delete all ReShade files" if complete else "Remove ReShade")
        self.review_hint.setText(
            "Permanently delete this ReShade installation, including modified configurations, presets, added shaders and logs."
            if complete
            else "Only unchanged files recorded by Vela are removed. Edited files are preserved."
        )
        self.summary.setText(
            "Installation directory:\n"
            + str(self.plan.executable.resolve().parent)
            + "\n\nRemove the ReShade DLL override from Steam launch options afterwards."
        )
        self.removal_files.setVisible(complete)
        if complete:
            try:
                names = reshade.complete_removal_files(self.plan.executable)
                self.removal_files.setPlainText(
                    "Files to delete (" + str(len(names)) + "):\n" + "\n".join(names)
                )
            except (OSError, ValueError) as error:
                self.complete_removal.setChecked(False)
                self.show_error(str(error))

    def start_job(self, remove):
        self.operation_active = True
        self.reset_after_close = False
        self.go(Page.INSTALL)
        self.log.clear()
        self.install_progress.setRange(0, 0)
        self.worker = InstallWorker(
            self.plan, remove, self, complete=remove and self.complete_removal.isChecked()
        )
        self.worker.progress.connect(self.append_progress, Qt.QueuedConnection)
        self.worker.result.connect(self.job_result, Qt.QueuedConnection)
        self.worker.failed.connect(self.job_error, Qt.QueuedConnection)
        self.worker.finished.connect(self.job_finished, Qt.QueuedConnection)
        self.worker.start()

    @Slot(str)
    def append_progress(self, message):
        self.log.appendPlainText(message)

    @Slot(object)
    def job_result(self, result):
        self.job_outcome = (True, result)

    @Slot(str)
    def job_error(self, message):
        self.job_outcome = (False, message)

    @Slot()
    def job_finished(self):
        self.operation_active = False
        success, result = self.job_outcome
        if self.reset_after_close:
            self.reset_defaults()
            return
        self.install_progress.setRange(0, 1)
        self.install_progress.setValue(1 if success else 0)
        if success:
            removing = self.worker.remove
            self.ready_heading.setText("ReShade removed" if removing else "ReShade is installed")
            self.ready_hint.setVisible(not removing)
            self.ready_hint.setText(
                "Paste these launch options into Steam → Properties → Launch Options. Vela does not change Steam settings automatically."
            )
            for widget in (self.command, self.copy_launch, self.game_directory):
                widget.setVisible(not removing)
            self.command.setPlainText("" if removing else self.final_command)
            self.ready_detail.setText(
                ("Removal complete. Modified files preserved: " + ", ".join(result))
                if removing and result
                else "Removal complete. Your other game files were preserved."
                if removing
                else "Start the game and press Home to open ReShade. Choose effects in-game. If shaders fail to compile, install d3dcompiler_47 in this game’s Proton prefix using Protontricks."
            )
            self.ready_removed = removing
            self.go(Page.GAME if self.reset_after_close else Page.READY)
            self.installed = not removing
            self.inspect_executable()
        else:
            self.go(Page.GAME if self.worker.remove else Page.REVIEW)
            self.show_error(result)
        self.removing = False

    def copy_command(self):
        QApplication.clipboard().setText(self.command.toPlainText())

    def open_directory(self):
        if self.plan:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.plan.executable.resolve().parent)))

    def busy(self):
        return bool(
            (self.worker and self.worker.isRunning())
            or (self.library_worker and self.library_worker.isRunning())
        )
