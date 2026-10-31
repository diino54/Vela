"""Offline Qt integration smoke; captures only this process's widgets."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
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
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='vela-ui-settings-') as preferences, \
            patch.object(Preview, 'start'), \
            patch.object(GoogleFonts, 'refresh'), \
            patch.object(GoogleFonts, 'queue_preview'), \
            patch.object(mangohud, 'discover', return_value=[]):
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, preferences)
        window = Window()
        try:
            window.resize(1400, 900)
            window.show()
            QTest.qWait(500)
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshots / 'main.png'))
            window.open_font_catalog('font_file')
            catalog = window.font_catalog
            wait_until(lambda: catalog.panel.isVisible() and not catalog.loading_fonts,
                       'Font catalog loader did not finish')
            wait_until(lambda: all(card.motion.opacity.opacity() == 1 for card in catalog.cards),
                       'Tile animations did not finish')
            assert not window.preview.isVisible()
            if args.screenshots:
                window.grab().save(str(args.screenshots / 'fonts.png'))
            catalog.select_category('Monospace')
            catalog.search.setText('JetBrains')
            wait_until(lambda: len(catalog.cards) == 1, 'Family filtering failed')
            weight = catalog.cards[0].weight
            assert weight.findData('700i') >= 0
            before = weight.currentIndex()
            event = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, -120),
                                Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
            app.sendEvent(weight, event)
            assert weight.currentIndex() == before, 'Wheel changed the font weight'
            catalog.search.setText('no-matching-font-family')
            assert catalog.empty.isVisible()
            # Interrupt close with reopen: stale loading/reveal timers must not hide it.
            catalog.dismiss()
            QTest.qWait(40)
            window.open_font_catalog('font_file_text')
            wait_until(lambda: catalog.panel.isVisible() and not catalog.loading_fonts,
                       'Reopening during close failed')
            QTest.keyClick(catalog.search, Qt.Key_Escape)
            wait_until(lambda: not catalog.isVisible(), 'Escape did not close the modal')
            assert window.preview.isVisible()
            with patch.object(window, 'apply_customization') as apply, \
                    patch.object(window, 'browse_customization_font') as browse:
                window.set_customization_font('font_file', '/tmp/vela-main-font.ttf')
                window.font_controls['font_file_text'].click()
                assert window.font_controls['font_file_text'].property('font_path') == '/tmp/vela-main-font.ttf'
                apply.assert_called_once()
                browse.assert_not_called()
        finally:
            window.preview.shutdown()
            window.close()
    print('PASS: layout, loader, filtering, wheel safety, interrupted modal, preview restoration, font reuse')


if __name__ == '__main__':
    main()
