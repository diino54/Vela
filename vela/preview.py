"""Embed a real OpenGL scene window through XWayland/X11.

Only the subprocess owned by this widget is stopped or reparented. Its private
MangoHud config and FG disable flags never affect a game or global settings.
"""
import ctypes as C
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QPainterPath, QRegion, QWindow
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget, QFrame
from . import mangohud


class XWindows:
    def __init__(self):
        self.lib = C.CDLL('libX11.so.6')
        definitions = {
            'XOpenDisplay': ([C.c_char_p], C.c_void_p),
            'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
            'XQueryTree': ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.POINTER(C.c_ulong)), C.POINTER(C.c_uint)], C.c_int),
            'XFetchName': ([C.c_void_p, C.c_ulong, C.POINTER(C.c_void_p)], C.c_int),
            'XFree': ([C.c_void_p], C.c_int),
            'XCloseDisplay': ([C.c_void_p], C.c_int),
            'XSync': ([C.c_void_p, C.c_int], C.c_int),
            'XSetErrorHandler': ([C.c_void_p], C.c_void_p),
            'XInternAtom': ([C.c_void_p, C.c_char_p, C.c_int], C.c_ulong),
            'XGetWindowProperty': ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_long, C.c_long,
                C.c_int, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int),
                C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.c_void_p)], C.c_int),
        }
        for name, (arguments, result) in definitions.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = arguments, result
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Cannot connect to XWayland.')
        # Desktop windows can disappear during enumeration. Ignore X11's
        # asynchronous BadWindow errors on this short-lived query connection.
        self.error_handler = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(lambda *_: 0)
        self.previous_handler = self.lib.XSetErrorHandler(C.cast(self.error_handler, C.c_void_p))

    def property(self, window, name):
        atom = self.lib.XInternAtom(self.display, name.encode(), 0)
        actual, count, remaining = C.c_ulong(), C.c_ulong(), C.c_ulong()
        format_bits, data = C.c_int(), C.c_void_p()
        result = self.lib.XGetWindowProperty(self.display, window, atom, 0, 1024,
            0, 0, C.byref(actual), C.byref(format_bits), C.byref(count), C.byref(remaining), C.byref(data))
        value = b''
        if result == 0 and data.value:
            # Xlib expands 32-bit properties into native unsigned longs.
            size = C.sizeof(C.c_ulong) if format_bits.value == 32 else max(1, format_bits.value // 8)
            value = C.string_at(data, count.value * size)
        if data.value:
            self.lib.XFree(data)
        return value

    def windows(self):
        root = self.lib.XDefaultRootWindow(self.display)
        pending, result = [root], {}
        while pending and len(result) < 4096:
            window = pending.pop()
            title = C.c_void_p()
            if self.lib.XFetchName(self.display, window, C.byref(title)) and title.value:
                result[window] = C.string_at(title).decode(errors='replace')
                self.lib.XFree(title)
            else:
                result[window] = self.property(window, '_NET_WM_NAME').decode(errors='replace')
            parent, root_out, count = C.c_ulong(), C.c_ulong(), C.c_uint()
            children = C.POINTER(C.c_ulong)()
            if self.lib.XQueryTree(self.display, window, C.byref(root_out), C.byref(parent), C.byref(children), C.byref(count)):
                if children:
                    pending.extend(children[i] for i in range(count.value))
                    self.lib.XFree(children)
        return result

    def close(self):
        if self.display:
            self.lib.XSync(self.display, 0)
            self.lib.XCloseDisplay(self.display)
            self.lib.XSetErrorHandler(self.previous_handler)
            self.display = None


class Preview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.closed = False
        self.setMinimumWidth(460)
        self.process = None
        self.connection = None
        self.container = None
        self.foreign = None
        self.directory = tempfile.TemporaryDirectory(prefix='vela-preview-')
        self.config = Path(self.directory.name) / 'scene.conf'
        self.animation_control = Path(self.directory.name) / 'animation.txt'
        self.notice_control = Path(self.directory.name) / 'notice.txt'
        self.set_paused(False)
        self.global_config = mangohud.default_config()
        self.options = (60, 'early', True)
        self.appearance = {}
        self.started = 0
        self.baseline = set()
        self.poll = QTimer(self)
        self.poll.setInterval(150)
        self.poll.timeout.connect(self.attach)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addStretch()
        self.frame = QFrame()
        self.frame.setObjectName('previewFrame')
        self.frame.setStyleSheet('#previewFrame { background: #1b1b1d; border: 1px solid #303033; border-radius: 10px; }')
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(1, 1, 1, 1)
        self.label = QLabel('3D preview')
        self.label.setStyleSheet('color: #aaaaaa; font-size: 14px; background: transparent;')
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.frame_layout.addWidget(self.label)
        self.notice_active = False
        layout.addWidget(self.frame)
        self.retry = QPushButton('Start preview')
        self.retry.setMaximumWidth(140)
        self.retry.clicked.connect(self.start)
        layout.addWidget(self.retry, alignment=Qt.AlignCenter)
        layout.addStretch()
        QTimer.singleShot(200, self.start)

    @property
    def pid(self):
        return self.process.pid if self.process and self.process.poll() is None else None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.frame.setFixedHeight(max(90, min(int((self.width() - 32) * 9 / 16), self.height() - 100)))

    def update_options(self, fps, method, show_hud):
        self.options = fps, method, show_hud
        try:
            base = self.global_config.read_text() if self.global_config.exists() else ''
            content = mangohud.managed_content(base, *self.options, self.appearance).encode()
        except (OSError, UnicodeError) as error:
            self.label.setText(f'Cannot read MangoHud configuration: {error}')
            return
        if self.config.exists():
            mangohud.replace_watched(self.config, content)
        else:
            self.config.write_bytes(content)

    def set_overlay(self, visible):
        fps, method, _ = self.options
        self.options = fps, method, visible
        content = self.config.read_text() if self.config.exists() else ''
        updated = mangohud.managed_content(content, *self.options).encode()
        if self.config.exists():
            mangohud.replace_watched(self.config, updated)
        else:
            self.config.write_bytes(updated)

    def set_paused(self, paused):
        self.animation_control.write_text('paused' if paused else 'running')

    def set_global_config(self, path, content=None):
        path = Path(path).expanduser().absolute()
        if content is None:
            content = path.read_bytes() if path.exists() else b''
        options = mangohud.values_from_content(content.decode('utf-8'))
        # Loading is a faithful copy, not an edit: preserve presets, unknown
        # options, repeated keys, FPS lists and values outside the UI ranges.
        if self.config.exists():
            mangohud.replace_watched(self.config, content)
        else:
            self.config.write_bytes(content)
        self.global_config = path
        self.options = options
        self.appearance = {}

    def round_preview(self):
        if self.container and self.foreign:
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.container.rect()), 9, 9)
            region = QRegion(path.toFillPolygon().toPolygon())
            self.container.setMask(region)
            self.foreign.setMask(region)

    def eventFilter(self, watched, event):
        if watched is self.container and event.type() == QEvent.Resize:
            self.round_preview()
        return super().eventFilter(watched, event)

    def prepare_notification(self, ready=None):
        self.notice_active = True
        if ready:
            ready()

    def set_notification_opacity(self, amount):
        # The scene draws its own veil, so its native window stays live.
        if self.closed:
            return
        self.notice_control.write_text(f'{float(amount):.4f}')

    def finish_notification(self):
        self.notice_active = False
        self.set_notification_opacity(0.)

    def start(self):
        if self.pid:
            return
        if QApplication.platformName() != 'xcb':
            self.label.setText('3D preview requires XWayland.\nStart Vela with QT_QPA_PLATFORM=xcb.')
            return
        cube = shutil.which('mangohud')
        if not cube:
            self.label.setText('Install MangoHud to enable the preview.')
            return
        try:
            self.stop()
            self.connection = XWindows()
            self.baseline = set(self.connection.windows())
            if not self.config.exists():
                self.set_global_config(self.global_config)
            env = dict(os.environ, MANGOHUD='1', MANGOHUD_CONFIGFILE=str(self.config),
                       VELA_ANIMATION_CONTROL=str(self.animation_control),
                       VELA_NOTICE_CONTROL=str(self.notice_control),
                       DISABLE_LSFGVK='1', DISABLE_AFMF='1', VELA_DISABLE='1')
            env.pop('MANGOHUD_CONFIG', None)
            from .runtime import available, library_directory
            if available():
                env['MANGOHUD_OPENGL_LIBS'] = str(library_directory() / 'libMangoHud_opengl.so')
            root = str(Path(__file__).resolve().parents[1])
            env['PYTHONPATH'] = root + os.pathsep + env.get('PYTHONPATH', '')
            self.log = open(Path(self.directory.name) / 'scene.log', 'a')
            self.process = subprocess.Popen([sys.executable, '-m', 'vela.preview_runner', str(os.getpid()),
                                            cube, '--dlsym', sys.executable, '-m', 'vela.scene'],
                                            env=env, stdout=self.log, stderr=self.log)
            self.started = time.monotonic()
            self.label.setText('Starting 3D preview…')
            self.retry.hide()
            self.poll.start()
        except (OSError, RuntimeError, ValueError, mangohud.ControlError) as error:
            self.stop()
            self.label.setText(str(error))
            self.retry.show()

    def attach(self):
        if not self.pid:
            self.stop()
            self.label.setText('3D preview stopped.\nTry starting it again.')
            self.retry.show()
            return
        if self.container:
            return
        windows = self.connection.windows()
        candidates = [window for window, title in windows.items()
                      if window not in self.baseline and title == 'Vela Preview']
        candidates = [window for window in candidates
                      if not (owner := self.connection.property(window, '_NET_WM_PID'))
                      or int.from_bytes(owner, sys.byteorder) == self.pid]
        if candidates:
            self.foreign = QWindow.fromWinId(candidates[0])
            self.container = QWidget.createWindowContainer(self.foreign, self.frame)
            self.container.installEventFilter(self)
            self.frame_layout.addWidget(self.container)
            self.label.hide()
            self.container.show()
            self.foreign.setGeometry(self.container.rect())
            self.round_preview()
        elif time.monotonic() - self.started > 12:
            self.stop()
            self.label.setText('Could not embed the 3D preview.')
            self.retry.show()

    def stop(self):
        self.poll.stop()
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None
        if self.container:
            self.container.hide()
            self.container.deleteLater()
            self.container = None
            self.foreign = None
        if self.connection:
            self.connection.close()
            self.connection = None
        if hasattr(self, 'log'):
            self.log.close()
        self.label.show()

    def shutdown(self):
        self.closed = True
        self.stop()
        self.directory.cleanup()
