"""Offline Qt integration smoke; captures only this process's widgets."""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vela import mangohud
from vela.google_fonts import GoogleFonts
from vela.preview import Preview
from vela.ui import Window


def wait_until(predicate, message, timeout=6):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(message)
        QTest.qWait(20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    with (
        tempfile.TemporaryDirectory(prefix="vela-ui-settings-") as preferences,
        patch.object(Preview, "start"),
        patch.object(GoogleFonts, "refresh"),
        patch.object(GoogleFonts, "queue_preview"),
        patch.object(mangohud, "discover", return_value=[]),
    ):
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, preferences)
        window = Window()
        try:
            window.resize(1400, 900)
            window.show()
            QTest.qWait(500)
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshots / "main.png"))
            for key, field in window.appearance_controls.items():
                expected = window.advanced_panel if key.startswith("vela_") else window.simple_panel
                assert expected.isAncestorOf(field), key
            assert window.settings_dialog.isAncestorOf(window.config_path)
            window.advanced.click()
            assert window.advanced_panel.isVisible() and not window.simple_panel.isVisible()
            window.simple.click()
            window.settings_button.click()
            settings = window.settings_dialog
            wait_until(lambda: settings.panel.isVisible(), "Settings modal did not open")
            assert not window.preview.isVisible()
            previous_config = window.config_path.text()
            test_config = Path(preferences) / "settings-smoke.conf"
            test_config.write_text("fps_limit=72\ntext_color=ABCDEF\n")
            window.config_path.setText(str(test_config))
            window.change_global_config()
            assert window.preview.global_config == test_config
            assert "fps_limit=72" in window.config_contents.toPlainText()
            assert test_config.read_text() == "fps_limit=72\ntext_color=ABCDEF\n"
            window.config_path.setText(previous_config)
            window.change_global_config()
            QTest.keyClick(settings, Qt.Key_Escape)
            wait_until(lambda: not settings.isVisible(), "Settings Escape did not close")
            assert window.preview.isVisible()
            window.preview_background.setCurrentIndex(
                window.preview_background.findData("daylight")
            )
            assert window.preview.background_control.read_text() == "daylight"
            assert not window.pause_preview.isEnabled()
            assert window.preferences.value("preview_background") == "daylight"
            assert "preview_background" not in window.customization_values()
            window.preview_background.setCurrentIndex(window.preview_background.findData("night"))
            assert window.preview.background_control.read_text() == "night"
            assert not window.pause_preview.isEnabled()
            from vela.sections import CollapsibleSection

            values = window.customization_values()
            section = window.collapsible_sections["Text"]
            section.toggle.click()
            assert section.body.isHidden() and window.customization_values() == values
            restored = CollapsibleSection("Text", QSettings("Vela", "Vela"), section.settings_key)
            assert not restored.toggle.isChecked() and restored.body.isHidden()
            restored.deleteLater()
            section.toggle.click()
            assert not section.body.isHidden()
            window.preview_background.setCurrentIndex(window.preview_background.findData("frosted"))
            assert window.preview.background_control.read_text() == "frosted"
            assert window.pause_preview.isEnabled()
            window.open_font_catalog("font_file")
            catalog = window.font_catalog
            wait_until(
                lambda: catalog.panel.isVisible() and not catalog.loading_fonts,
                "Font catalog loader did not finish",
            )
            wait_until(
                lambda: all(card.motion.opacity.opacity() == 1 for card in catalog.cards),
                "Tile animations did not finish",
            )
            assert not window.preview.isVisible()
            if args.screenshots:
                window.grab().save(str(args.screenshots / "fonts.png"))
            catalog.select_category("Monospace")
            catalog.search.setText("JetBrains")
            wait_until(lambda: len(catalog.cards) == 1, "Family filtering failed")
            weight = catalog.cards[0].weight
            assert weight.findData("700i") >= 0
            before = weight.currentIndex()
            event = QWheelEvent(
                QPointF(10, 10),
                QPointF(10, 10),
                QPoint(),
                QPoint(0, -120),
                Qt.NoButton,
                Qt.NoModifier,
                Qt.NoScrollPhase,
                False,
            )
            app.sendEvent(weight, event)
            assert weight.currentIndex() == before, "Wheel changed the font weight"
            catalog.search.setText("no-matching-font-family")
            assert catalog.empty.isVisible()
            # Interrupt close with reopen: stale loading/reveal timers must not hide it.
            catalog.dismiss()
            QTest.qWait(40)
            window.open_font_catalog("font_file_text")
            wait_until(
                lambda: catalog.panel.isVisible() and not catalog.loading_fonts,
                "Reopening during close failed",
            )
            QTest.keyClick(catalog.search, Qt.Key_Escape)
            wait_until(lambda: not catalog.isVisible(), "Escape did not close the modal")
            assert window.preview.isVisible()
            with (
                patch.object(window, "apply_customization") as apply,
                patch.object(window, "browse_customization_font") as browse,
            ):
                window.set_customization_font("font_file", "/tmp/vela-main-font.ttf")
                window.font_controls["font_file_text"].click()
                assert window.font_controls["font_file_text"].property("font_path") == ""
                assert window.font_controls["font_file_text"].text() == "Same as main font"
                apply.assert_not_called()
                browse.assert_called_once_with("font_file_text")
                window.set_customization_font("font_file_text", "/tmp/vela-main-font.ttf")
                assert window.font_controls["font_file_text"].property("font_path") == ""
        finally:
            window.preview.shutdown()
            window.close()
    print(
        "PASS: layout, loader, filtering, wheel safety, interrupted modal, preview restoration, font reuse"
    )


if __name__ == "__main__":
    main()
