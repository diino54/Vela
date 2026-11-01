"""Owned Qt modal with a local subprocess fixture; no desktop queries or settings writes."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QProcess, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vela import mangohud
from vela.metric_cards import MetricCard
from vela.preview import Preview
from vela.ui import Window

app = QApplication([])
with (
    tempfile.TemporaryDirectory() as temp,
    patch.object(Preview, "start"),
    patch.object(mangohud, "discover", return_value=[]),
):
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, temp)
    w = Window()
    w.timer.stop()
    w.show()
    d = w.hdr_dialog
    helper = Path(temp) / "kscreen-fixture"
    helper.write_text(
        '#!/usr/bin/env python3\nprint(\'{"outputs":[{"name":"DP-1","connected":true,"hdr":true,"wcg":true}]}\')\n'
    )
    helper.chmod(0o755)
    with patch("vela.hdr_dialog.shutil.which", return_value=str(helper)):
        w.open_hdr()
        for _ in range(100):
            QTest.qWait(20)
            if not d.pending:
                break
        QTest.qWait(450)
        assert "HDR: Enabled" in d.report.toPlainText(), d.report.toPlainText()
        assert any(
            card.accessibleName() == "HDR Status: Enabled"
            for card in d.card_body.findChildren(MetricCard)
        )
        assert not w.preview.isVisible()
        assert d.panel.width() <= 900 and d.panel.height() <= 680
        d.copy_report()
        assert "HDR: Enabled" in app.clipboard().text()
        if "--screenshots" in sys.argv:
            w.grab().save("/tmp/vela-hdr-diagnostics.png")
        d.dismiss()
        QTest.qWait(350)
        assert w.preview.isVisible()
    with patch("vela.hdr_dialog.shutil.which", return_value=None):
        d.open()
        QTest.qWait(450)
        assert "Unknown" in d.report.toPlainText() and d.refresh.isEnabled()
        cards = d.card_body.findChildren(MetricCard)
        assert any(card.accessibleName() == "HDR Status: Unknown" for card in cards)
        assert not any(card.accessibleName() == "HDR Status: Enabled" for card in cards)
        d.dismiss()
        QTest.qWait(350)
    helper.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(10)\n")
    with patch("vela.hdr_dialog.shutil.which", return_value=str(helper)):
        d.open()
        QTest.qWait(450)
        d.expired()
        QTest.qWait(100)
        assert "timed out" in d.status.text() and not d.pending
        assert d.process.state() == QProcess.NotRunning
        d.refresh.click()
        QTest.qWait(100)
        d.dismiss()
        QTest.qWait(350)
        assert d.process.state() == QProcess.NotRunning
    w.close()
print("PASS: HDR snapshot, unknown fallback, timeout, copy, modal lifecycle and process cleanup")
