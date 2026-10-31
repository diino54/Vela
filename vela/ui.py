"""Main-window actions and lifecycle; runnable entry point: python -m vela.ui.

Layout: window_layout.py. Reusable controls: controls.py. Theme: theme.py.
Appearance edits affect the private preview until Save configuration is used.
"""
import os
import signal
import sys
import time
from pathlib import Path

# Foreign Vulkan windows can be embedded by Qt's xcb backend, including on KDE
# Wayland through XWayland. Explicit platform overrides (e.g. tests) are retained.
if os.environ.get('DISPLAY'):
    os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from PySide6.QtCore import QLocale, QPoint, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QFontDatabase, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QFileDialog, QColorDialog, QWidget
from . import mangohud, layer_order
from .panels import FrostedPanel


from .controls import (PopupDelegate, NoWheelComboBox, ApplicationComboBox, PathEdit, NoWheelSpinBox, DependencyRow, NumberControl, ScrollFade, SettingsScroll)
from .theme import apply_theme, paint_window_background
from .window_layout import build_window


class Window(QWidget):
    """Own selected game, preview state, configuration actions and shutdown."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Vela')
        self.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/vela.svg')))
        self.setMinimumSize(1060, 600)
        self.resize(1400, 780)
        apply_theme(self)
        build_window(self)
        self.sessions = []
        self.pending = None
        self.message_until = 0
        self.apply.clicked.connect(lambda: self.write(self.fps.value()))
        self.loading_customization = False
        for field in self.appearance_controls.values():
            field.valueChanged.connect(self.apply_customization)
        for checkbox in self.metric_controls.values():
            checkbox.toggled.connect(self.apply_customization)
        for checkbox in self.text_controls.values():
            checkbox.toggled.connect(self.apply_customization)
        self.disable.clicked.connect(self.disable_limit)
        try:
            self.load_global_preview()
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot load global configuration: {error}')
        self.selection_changed()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def restart_scene(self):
        self.preview.stop()
        self.preview.start()

    def toggle_preview_options(self):
        if self.preview_menu.isVisible():
            self.preview_menu.hide()
            return
        self.preview_menu.ensurePolished()
        size = self.preview_menu.sizeHint()
        position = self.preview_options.mapToGlobal(QPoint(
            (self.preview_options.width() - size.width()) // 2, -size.height() - 8))
        available = self.screen().availableGeometry()
        position.setX(max(available.left(), min(position.x(), available.right() - size.width() + 1)))
        position.setY(max(available.top(), position.y()))
        self.preview_options.setChecked(True)
        self.preview_menu.popup(position)

    def paintEvent(self, event):
        paint_window_background(self)

    # Configuration loading, destination selection and explicit persistence.
    def update_config_contents(self):
        path = Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser()
        try:
            content = path.read_text()
            self.config_contents.setPlainText(content if content.strip() else '# Empty configuration')
        except (OSError, UnicodeError) as error:
            self.config_contents.setPlainText(f'# Cannot read configuration: {error}')

    def change_global_config(self):
        value = self.config_path.text().strip() or str(mangohud.default_config())
        self.config_path.setText(value)
        self.preferences.setValue('global_config', value)
        self.load_global_preview()
        if hasattr(self, 'sessions'):
            self.selection_changed()
        self.update_config_contents()

    def configuration_target(self):
        session = self.selected()
        if session is not None and session.pid != self.preview.pid and session.profile.is_file():
            return session.profile.absolute()
        return Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser().absolute()

    def update_configuration_button(self):
        path = self.configuration_target()
        different = path != self.preview.global_config
        changed = self.configuration_has_changes(path) if not different else False
        self.save_config.setText(('Load game config' if self.selected() and path == self.selected().profile.absolute()
                                  else 'Load global config') if different else
                                 ('Save configuration' if changed else 'No changes to save'))
        self.save_config.setEnabled(different or changed)
        self.save_config.setStyleSheet(
            'QPushButton#apply { background: #a83232; border-color: #c64545; }'
            'QPushButton#apply:hover { background: #bd3b3b; }'
            'QPushButton#apply:pressed { background: #862828; }' if different else
            ('QPushButton#apply:disabled { background: #303030; color: #888888; border-color: #414141; }'
             if not changed else ''))
        self.save_config.setToolTip(
            f'{"A different configuration is available. Load it into the preview" if different else "Save appearance and metrics" if changed else "No changes to save — settings match this file"}:\n{path}')
        choosing = self.status.actions is not None
        self.save_config.setEnabled((different or changed) and not choosing)
        self.save_glow.set_active(changed and not different and not choosing)
        for widget, effect in zip(self.configuration_controls, self.configuration_fades):
            widget.setEnabled(not different and not choosing)
            effect.setOpacity(.5 if different else .7 if choosing else 1.)
        session = self.selected()
        available = session is not None and not session.reason and not different and not choosing
        self.apply.setEnabled(available)
        self.disable.setEnabled(available)

    def configuration_has_changes(self, path):
        try:
            if not path.exists():
                return True
            content = path.read_text()
            if any(button.property('font_path') != mangohud.font_values(content)[key]
                   for key, button in self.font_controls.items()):
                return True
            appearance = mangohud.appearance_values(content)
            for key, field in self.appearance_controls.items():
                scale = 100 if key in ('background_alpha', 'alpha', 'vela_background_noise', 'vela_border_alpha', 'vela_shadow_alpha') else 1
                if field.value() != round(appearance[key] * scale, field.decimals()):
                    return True
            if any(button.property('color') != mangohud.color_values(content)[key]
                   for key, button in self.color_controls.items()):
                return True
            if any(field.isChecked() != mangohud.text_values(content)[key]
                   for key, field in self.text_controls.items()):
                return True
            return any(field.isChecked() != mangohud.metric_values(content)[key]
                       for key, field in self.metric_controls.items())
        except (OSError, ValueError):
            return True

    def configuration_action(self):
        try:
            path = self.configuration_target()
            if path != self.preview.global_config:
                # Read first so an unreadable profile leaves the preview intact.
                path.read_text()
                self.selection_changed()
                self.load_preview_configuration(path)
                self.status.show_message('Configuration loaded', path)
                self.message_until = time.monotonic() + 6
            else:
                self.save_configuration()
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot load configuration: {error}')
            self.message_until = time.monotonic() + 6
        self.update_configuration_button()

    def save_configuration(self, destination=None, expected_identity=None):
        try:
            global_path = Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser().absolute()
            session = self.selected()
            if expected_identity is not None and (session is None or session.identity != expected_identity):
                self.status.setText('Application changed. Choose where to save again.')
                return
            path = global_path
            if session is not None and session.pid != self.preview.pid:
                if destination is None:
                    self.choose_save_destination(session, global_path)
                    return
                if destination == 'profile':
                    if session.profile.is_symlink():
                        raise mangohud.ControlError('The MangoHud profile is a symlink; the shared file will not be changed.')
                    path = session.profile.absolute()
            appearance = self.customization_values()
            appearance.update({key: int(field.isChecked()) for key, field in self.metric_controls.items()})
            mangohud.save_appearance(path, appearance, template=global_path)
            if path == global_path:
                self.load_global_preview()
                self.update_config_contents()
            else:
                self.load_preview_configuration(path)
            self.status.show_message('Game profile saved' if path != global_path else 'Global configuration saved', path)
            self.status.setToolTip(str(path))
        except (mangohud.ControlError, OSError, ValueError, UnicodeError) as error:
            self.status.setText(f'Cannot save configuration: {error}')
        self.message_until = time.monotonic() + 10
        self.update_configuration_button()

    def choose_save_destination(self, session, global_path):
        identity = session.identity
        self.status.show_choice(
            session.name, global_path, session.profile,
            lambda: self.save_configuration('global', identity),
            lambda: self.save_configuration('profile', identity),
            self.status.dismiss,
        )
        self.message_until = 0
        self.update_configuration_button()

    def finish_save_choice(self):
        self.message_until = 0
        if hasattr(self, 'sessions'):
            self.update_configuration_button()

    # Optional LSFG layer-order integration.
    def show_lsfg_help(self):
        self.status.show_message(
            'How Fix LSFG works',
            'Places MangoHud before LSFG so the limiter and FPS counter use base frames.\n'
            'Click Fix LSFG to enable it, then restart the game.\n'
            'Use the trash icon to remove the fix, then restart the game again.\n'
            'It does not enable frame generation or change the LSFG multiplier.',
            duration=15000,
        )
        self.message_until = time.monotonic() + 15

    def configure_lsfg(self):
        try:
            path = layer_order.configure()
            self.status.setText('LSFG order configured. Restart the game.')
            self.status.setToolTip(str(path))
        except (OSError, ValueError, KeyError) as error:
            self.status.setText(str(error))
        self.update_lsfg_status()
        self.message_until = time.monotonic() + 10

    def remove_lsfg_fix(self):
        try:
            layer_order.remove()
            self.status.setText('LSFG fix removed. Restart the game.')
        except (OSError, ValueError) as error:
            self.status.setText(f'Cannot remove LSFG fix: {error}')
        self.update_lsfg_status()
        self.message_until = time.monotonic() + 10

    def update_lsfg_status(self):
        state, description = layer_order.configuration_status()
        self.fix_lsfg.setText({
            'missing': 'Fix LSFG',
            'enabled': 'LSFG fix enabled',
            'invalid': 'Repair LSFG fix',
            'foreign': 'LSFG config in use',
        }[state])
        self.fix_lsfg.setEnabled(state in ('missing', 'invalid'))
        self.fix_lsfg.setToolTip(description)
        self.remove_lsfg.setVisible(state == 'enabled')

    def open_configuration_directory(self):
        path = Path(self.config_path.text().strip() or str(mangohud.default_config())).expanduser().absolute().parent
        if not path.is_dir():
            self.status.setText('Configuration directory does not exist.')
            self.message_until = time.monotonic() + 6
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.status.setText('Could not open the configuration directory.')
            self.message_until = time.monotonic() + 6

    def choose_global_config(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Global MangoHud configuration',
            str(Path(self.config_path.text()).expanduser()), 'Configuration files (*.conf);;All files (*)')
        if path:
            self.config_path.setText(path)
            self.change_global_config()

    # Preview lifecycle and selected-process synchronization.
    def update_preview(self, *_):
        self.preview.update_options(self.fps.value(), self.method.currentData(), self.show_hud.isChecked())

    def load_global_preview(self):
        path = Path(self.config_path.text()).expanduser().absolute()
        self.load_preview_configuration(path)

    def load_preview_configuration(self, path):
        content = path.read_bytes() if path.exists() else b''
        _, _, visible = mangohud.values_from_content(content.decode('utf-8'))
        self.preview.set_global_config(path, content=content)
        self.show_hud.blockSignals(True)
        self.show_hud.setChecked(visible)
        self.show_hud.blockSignals(False)
        self.update_preview_source(path)

    def update_preview_source(self, path):
        global_path = Path(self.config_path.text()).expanduser().absolute()
        name = 'Global configuration' if path == global_path else path.name
        self.preview_source.full_text = f'Preview · {name}'
        self.preview_source.setToolTip(str(path))
        self.preview_source.setText(self.preview_source.fontMetrics().elidedText(
            self.preview_source.full_text, Qt.ElideMiddle, self.preview_source.width()))

    def closeEvent(self, event):
        size = self.normalGeometry().size() if self.isMaximized() or self.isFullScreen() else self.size()
        self.preferences.setValue('window_width', max(self.minimumWidth(), size.width()))
        self.preferences.setValue('window_height', max(self.minimumHeight(), size.height()))
        self.preferences.sync()
        self.timer.stop()
        self.status.motion.stop()
        self.status.expiry.stop()
        self.status.hide()
        self.preview.shutdown()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.status.actions is not None:
            self.status.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def selected(self):
        identity = self.process.currentData()
        return next((session for session in self.sessions if session.identity == identity), None)

    def selected_config(self):
        global_path = Path(self.config_path.text()).expanduser().absolute()
        session = self.selected()
        if session is None or session.pid == self.preview.pid:
            return global_path
        return mangohud.profile_config(session, global_path) or global_path

    def selection_changed(self):
        if not hasattr(self, 'sessions'):
            return
        if self.status.actions is not None:
            self.status.dismiss()
        self.pending = None
        self.message_until = 0
        self.loading_customization = True
        try:
            path = self.selected_config()
            content = path.read_text() if path.exists() else ''
            fps, method, visible = mangohud.config_values(path)
            for key, value in mangohud.font_values(content).items():
                self.set_customization_font(key, value)
            for key, enabled in mangohud.metric_values(content).items():
                self.metric_controls[key].setChecked(enabled)
            for key, color in mangohud.color_values(content).items():
                self.set_customization_color(key, color)
            for key, enabled in mangohud.text_values(content).items():
                self.text_controls[key].setChecked(enabled)
            appearance = mangohud.appearance_values(content)
            for key, field in self.appearance_controls.items():
                value = appearance[key] * (100 if key in ('background_alpha', 'alpha', 'vela_background_noise', 'vela_border_alpha', 'vela_shadow_alpha') else 1)
                decimals = min(3, len(str(value).partition('.')[2].rstrip('0')))
                field.setDecimals(max(field.decimals(), decimals))
                field.setRange(min(field.minimum(), value), max(field.maximum(), value))
                field.setValue(value)
            self.fps.setValue(fps if 0 <= fps <= 1000 else 0)
            self.method.setCurrentIndex(1 if method == 'late' else 0)
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot load application configuration: {error}')
            self.message_until = time.monotonic() + 6
        finally:
            self.loading_customization = False
            self.update_configuration_button()

    # Appearance actions: update preview first; save only on request.
    def set_customization_color(self, key, value):
        button = self.color_controls[key]
        button.setProperty('color', value)
        button.setText(f'#{value}')
        icon = QPixmap(18, 18)
        icon.fill(QColor(f'#{value}'))
        button.setIcon(QIcon(icon))

    def choose_customization_color(self, key):
        button = self.color_controls[key]
        color = QColorDialog.getColor(QColor('#' + button.property('color')), self, button.accessibleName())
        if color.isValid():
            self.set_customization_color(key, color.name()[1:].upper())
            self.apply_customization()

    def customization_values(self):
        values = {key: field.value() / (100 if key in ('background_alpha', 'alpha', 'vela_background_noise', 'vela_border_alpha', 'vela_shadow_alpha') else 1)
                  for key, field in self.appearance_controls.items()}
        values.update({key: button.property('color') for key, button in self.color_controls.items()})
        values.update({key: int(field.isChecked()) for key, field in self.text_controls.items()})
        values.update({key: button.property('font_path') for key, button in self.font_controls.items()})
        return values

    def set_customization_font(self, key, path):
        button = self.font_controls[key]
        button.setProperty('font_path', path)
        label = Path(path).name if path else ('Default font' if key == 'font_file' else 'Same as main font')
        button.setText(button.fontMetrics().elidedText(label, Qt.ElideMiddle, 145))
        hint = ('Click to use the main font. Right-click to choose a TTF/OTF file.'
                if key == 'font_file_text' else 'Choose a TTF/OTF file.')
        button.setToolTip((path or label) + '\n' + hint + ' Use Restart preview if the font does not refresh.')

    def open_font_catalog(self, key):
        from .font_catalog import FontCatalog
        if not hasattr(self, 'font_catalog'):
            self.font_catalog = FontCatalog(self, self.use_catalog_font)
        self.font_catalog.open(key)

    def use_catalog_font(self, key, path):
        self.set_customization_font(key, path)
        self.apply_customization()

    def choose_customization_font(self, key):
        if key == 'font_file_text':
            main = self.font_controls['font_file'].property('font_path')
            if main:
                self.set_customization_font(key, main)
                self.apply_customization()
                return
        self.browse_customization_font(key)

    def show_font_file_menu(self, key, position):
        menu = QMenu(self)
        menu.addAction('Choose font file…', lambda: self.browse_customization_font(key))
        menu.exec(self.font_controls[key].mapToGlobal(position))

    def browse_customization_font(self, key):
        current = self.font_controls[key].property('font_path')
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose font',
            current or str(Path.home() / '.local/share/fonts'), 'Fonts (*.ttf *.otf *.TTF *.OTF)')
        if not filename:
            return
        path = Path(filename).expanduser().absolute()
        try:
            if path.suffix.lower() not in ('.ttf', '.otf') or not path.is_file():
                raise ValueError('Choose an existing TTF or OTF font file.')
            mangohud.managed_content('', 0, 'early', True, {key: str(path)})
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id < 0:
                raise ValueError('This file could not be loaded as a font.')
            QFontDatabase.removeApplicationFont(font_id)
            self.set_customization_font(key, str(path))
            self.apply_customization()
        except (OSError, ValueError, mangohud.ControlError) as error:
            self.status.setText(f'Cannot use font: {error}')
            self.message_until = time.monotonic() + 6

    def reset_customization_font(self, key):
        self.set_customization_font(key, '')
        self.apply_customization()

    def apply_customization(self, *_):
        if self.loading_customization:
            return
        try:
            options = self.customization_values()
            options.update({key: int(field.isChecked()) for key, field in self.metric_controls.items()})
            # Only the private preview changes until Save configuration is used.
            self.preview.appearance = options
            self.preview.update_options(*self.preview.options)
        except (mangohud.ControlError, OSError, ValueError) as error:
            self.status.setText(str(error))
            self.message_until = time.monotonic() + 6
        finally:
            self.update_configuration_button()

    # Live FPS limiter updates and process polling.
    def disable_limit(self):
        self.fps.setValue(0)
        self.write(0)

    def write(self, fps, include_hud=False):
        session = self.selected()
        if session is None:
            return
        try:
            _, _, saved_hud = mangohud.config_values(self.selected_config())
            appearance = None
            if include_hud:
                appearance = self.customization_values()
                appearance.update({key: int(field.isChecked()) for key, field in self.metric_controls.items()})
            target = mangohud.apply(session, fps, self.method.currentData(), saved_hud, appearance, global_config=self.config_path.text())
            self.preview.update_options(fps, self.method.currentData(), self.show_hud.isChecked())
            self.pending = (session.identity, target, fps, self.method.currentData(), time.monotonic())
            self.status.setText('Applying settings…')
            self.message_until = 0
        except (mangohud.ControlError, OSError, ValueError) as error:
            self.status.setText(str(error))
            self.message_until = time.monotonic() + 6

    def refresh(self):
        self.update_lsfg_status()
        identity = self.process.currentData()
        self.sessions = mangohud.discover()
        entries = [(f'{"3D scene (preview)" if session.pid == self.preview.pid else session.name} · PID {session.pid}',
                    session.identity) for session in self.sessions]
        old = [(self.process.itemText(i), self.process.itemData(i))
               for i in range(self.process.count())]
        if old != entries:
            self.process.blockSignals(True)
            self.process.clear()
            for label, identity_key in entries:
                self.process.addItem(label, identity_key)
            index = next((i for i, session in enumerate(self.sessions) if session.identity == identity), 0)
            self.process.setCurrentIndex(index)
            self.process.blockSignals(False)
            if self.process.currentData() != identity:
                self.selection_changed()
        self.process.setToolTip(self.process.currentText())
        session = self.selected()
        available = session is not None and not session.reason
        self.apply.setEnabled(available)
        self.disable.setEnabled(available)
        self.process.setToolTip(session.reason if session and session.reason else self.process.currentText())
        self.update_configuration_button()
        if self.status.actions is not None or time.monotonic() < self.message_until:
            return
        if self.pending and session and not session.reason:
            selected, target, fps, method, started = self.pending
            if session.identity != selected:
                self.pending = None
            elif session.watched == target:
                limit = f'{fps:g} FPS' if fps else 'Unlimited FPS'
                pacing = 'Early · smooth pacing' if method == 'early' else 'Late · low latency'
                self.status.show_message('Applied successfully', f'{limit} · {pacing}')
                self.pending = None
                self.message_until = time.monotonic() + 5
            elif time.monotonic() - started > 3:
                self.status.setText('MangoHud did not switch profiles. Limit unconfirmed.')
                self.pending = None
                self.message_until = time.monotonic() + 6


def main():
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app = QApplication(sys.argv)
    app.setApplicationName('Vela')
    app.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/vela.svg')))
    app.setDesktopFileName('vela')
    window = Window()
    app.aboutToQuit.connect(window.preview.shutdown)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
