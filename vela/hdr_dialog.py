"""Compact HDR diagnostics modal; asynchronous, bounded read-only KScreen query."""

import os
import shutil

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .controls import SettingsScroll
from .hdr import LIMITS, connected_outputs, desktop_report, display_metrics, kscreen_report
from .metric_cards import MetricGrid
from .modal import FrostedModal


class HdrDialog(FrostedModal):
    def __init__(self, owner):
        super().__init__(owner)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel("HDR diagnostics")
        title.setObjectName("panelTitle")
        header.addWidget(title, 1)
        close = QPushButton("Close  ×")
        close.clicked.connect(self.dismiss)
        header.addWidget(close)
        layout.addLayout(header)
        hint = QLabel(
            "Session, displays and HDR state reported by your desktop. No settings are changed."
        )
        hint.setWordWrap(True)
        hint.setObjectName("fontMeta")
        layout.addWidget(hint)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.report = QPlainTextEdit(self)
        self.report.setReadOnly(True)
        self.report.setAccessibleName("HDR diagnostic report")
        self.report.setStyleSheet(
            "QPlainTextEdit { background: #111; color: #ddd; border: 1px solid #333; border-radius: 8px; padding: 12px; }"
        )
        self.report.hide()  # Keep a plain-text export separate from the card view.
        self.scroll = SettingsScroll()
        self.scroll.setObjectName("fontCatalogScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.viewport().setAutoFillBackground(False)
        self.card_body = QFrame()
        self.card_body.setObjectName("fontCatalogContent")
        self.cards_layout = QVBoxLayout(self.card_body)
        self.cards_layout.setContentsMargins(0, 0, 10, 0)
        self.cards_layout.setSpacing(16)
        self.scroll.setWidget(self.card_body)
        layout.addWidget(self.scroll, 1)
        limits = QLabel(LIMITS)
        limits.setWordWrap(True)
        limits.setObjectName("fontMeta")
        layout.addWidget(limits)
        footer = QHBoxLayout()
        self.copy = QPushButton("Copy report")
        self.copy.clicked.connect(self.copy_report)
        footer.addWidget(self.copy)
        footer.addStretch()
        self.refresh = QPushButton("Refresh")
        self.refresh.setObjectName("apply")
        self.refresh.clicked.connect(self.scan)
        footer.addWidget(self.refresh)
        layout.addLayout(footer)
        self.process = QProcess(self)
        self.process.finished.connect(self.completed)
        self.process.errorOccurred.connect(self.failed)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(6000)
        self.timeout.timeout.connect(self.expired)
        self.pending = False

    def fit_panel(self):
        self.setGeometry(self.parentWidget().rect())
        width, height = min(900, max(0, self.width() - 48)), min(680, max(0, self.height() - 48))
        self.panel.setGeometry(
            (self.width() - width) // 2, (self.height() - height) // 2, width, height
        )
        self.target_rect = self.panel.geometry()

    def open(self):
        if not self.isVisible() or self.closing:
            self.scan()
        super().open()

    def scan(self):
        if self.process.state() != QProcess.NotRunning:
            return
        self.base = desktop_report() + "\n\nQT DISPLAY VIEW\n"
        self.base += f"Vela platform: {QApplication.platformName()}\n"
        for screen in QApplication.screens():
            size = screen.size()
            self.base += f"{screen.name()}: {size.width()}×{size.height()} logical px · {screen.refreshRate():g} Hz · scale {screen.devicePixelRatio():g}×\n"
        self.base += "Qt geometry is the application view, not proof of HDR.\n\n"
        self.outputs = []
        self.report.setPlainText(self.base + "Reading desktop HDR state…")
        self.render_cards("Checking…")
        self.status.setText("Checking displays…")
        command = shutil.which("kscreen-doctor")
        if not command:
            self.finish(
                "KScreen is not installed. Desktop HDR state: Unknown.",
                "Partial report · KScreen unavailable",
            )
            return
        self.pending = True
        self.refresh.setEnabled(False)
        # Vela may use xcb to embed its preview in a Wayland session. Query
        # the real session instead of inheriting that app-only override.
        env = QProcessEnvironment.systemEnvironment()
        platform = (
            "wayland"
            if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY")
            else "xcb"
        )
        env.insert("QT_QPA_PLATFORM", platform)
        self.process.setProcessEnvironment(env)
        self.process.start(command, ["-j"])
        self.timeout.start()

    def finish(self, text, status):
        self.pending = False
        self.timeout.stop()
        self.refresh.setEnabled(True)
        self.status.setText(status)
        self.report.setPlainText(self.base + text)
        self.render_cards()

    def completed(self, code, exit_status):
        if not self.pending:
            return
        if code != 0 or exit_status != QProcess.NormalExit:
            self.finish(
                "KScreen could not read the desktop. HDR state: Unknown.",
                "Partial report · desktop query failed",
            )
            return
        try:
            raw = bytes(self.process.readAllStandardOutput()).decode("utf-8")
            self.outputs = connected_outputs(raw)
            text = kscreen_report(raw)
        except (ValueError, UnicodeError):
            self.finish(
                "KScreen returned an unreadable snapshot. HDR state: Unknown.",
                "Partial report · invalid desktop response",
            )
            return
        self.finish(text, "Report ready · desktop snapshot")

    def render_cards(self, unknown="Unknown"):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        def group(title, metrics):
            heading = QLabel(title)
            heading.setTextFormat(Qt.PlainText)
            heading.setObjectName("panelTitle")
            heading.setStyleSheet("color: #eee; font-size: 14px; font-weight: 600;")
            self.cards_layout.addWidget(heading)
            self.cards_layout.addWidget(MetricGrid(metrics))

        if self.outputs:
            for output in self.outputs:
                group(
                    str(output.get("name") or "Display") + " · Desktop HDR", display_metrics(output)
                )
        else:
            group(
                "Desktop HDR",
                [("HDR Status", unknown, "monitor"), ("Wide Color Gamut", unknown, "color")],
            )
        driver = self.base.split("GPU DRIVERS\n", 1)[-1].split("\n", 1)[0]
        group(
            "System",
            [
                ("Session", os.environ.get("XDG_SESSION_TYPE") or "Unknown", "session"),
                ("Desktop", os.environ.get("XDG_CURRENT_DESKTOP") or "Unknown", "session"),
                ("GPU Driver", driver, "gpu"),
                ("Vela Platform", QApplication.platformName(), "session"),
            ],
        )
        # Qt screens remain useful when the compositor backend is unavailable;
        # label the source so its logical geometry is not mistaken for HDR data.
        if not self.outputs:
            for screen in QApplication.screens():
                size = screen.size()
                group(
                    (screen.name() or "Display") + " · Qt view",
                    [
                        ("Logical Size", f"{size.width()} × {size.height()} px", "monitor"),
                        ("Refresh Rate", f"{screen.refreshRate():.2f} Hz", "refresh"),
                        ("Scale", f"{screen.devicePixelRatio():g}×", "scale"),
                    ],
                )
        self.cards_layout.addStretch()

    def failed(self, error):
        if self.pending:
            self.finish(
                "KScreen is unavailable or failed to start. HDR state: Unknown.",
                "Partial report · desktop query failed",
            )

    def expired(self):
        self.finish(
            "KScreen did not respond within 6 seconds. HDR state: Unknown.",
            "Partial report · desktop query timed out",
        )
        self.process.kill()

    def stop(self):
        self.pending = False
        self.timeout.stop()
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        self.refresh.setEnabled(True)

    def dismiss(self):
        self.stop()
        super().dismiss()

    def copy_report(self):
        QApplication.clipboard().setText(
            "Vela HDR diagnostics\n\n" + self.report.toPlainText() + "\n\n" + LIMITS
        )
