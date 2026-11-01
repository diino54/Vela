"""Exercise the actual modal and threaded install/removal with offline fixtures."""

import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_reshade import download, pe

from vela import mangohud, reshade
from vela.preview import Preview
from vela.ui import Window

app = QApplication([])
original_install = reshade.install
with (
    tempfile.TemporaryDirectory() as temp,
    patch.object(Preview, "start"),
    patch.object(mangohud, "discover", return_value=[]),
    patch.object(reshade, "steam_games", return_value=[]),
    patch.object(reshade, "rounded_available", return_value=True),
    patch.object(reshade, "rounded_runtime", return_value=("6.8.0", pe())),
    patch.object(
        reshade,
        "install",
        side_effect=lambda plan, report: original_install(plan, report, download),
    ),
):
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, temp)
    exe = Path(temp) / "Game.exe"
    exe.write_bytes(pe())
    w = Window()
    w.timer.stop()
    w.show()
    w.open_reshade()
    QTest.qWait(500)
    d = w.reshade_dialog
    assert d.isVisible() and not w.preview.isVisible()
    # A selected target can disappear before a queued Configure transition.
    vanished = Path(temp) / "Vanished.exe"
    vanished.write_bytes(pe())
    d.choose_mode("configure")
    d.executable.setText(str(vanished))
    vanished.unlink()
    d.configure_target()
    assert d.step == 0 and d.validation_glows[d.executable].active
    d.reset_defaults()

    assert d.step == 5 and d.install_choice.isVisible() and d.configure_choice.isVisible()
    assert d.panel.width() <= 720 and d.panel.height() <= 380
    if "--screenshots" in sys.argv:
        w.grab().save("/tmp/vela-reshade-home.png")
    d.install_choice.click()
    assert d.step == 0
    assert d.next.isEnabled() and d.next.property("awaitingChoice")
    d.advance()
    assert d.step == 0 and not d.error.isVisible()
    assert d.validation_glows[d.executable].active
    glow = d.validation_glows[d.executable]
    QTest.qWait(1200)
    assert glow.active and not glow.effect.isEnabled()
    assert glow.intro.state().name == "Stopped"
    d.advance()
    assert glow.effect.isEnabled() and glow.intro.currentTime() < 100
    d.executable.setText(str(exe))
    assert not d.next.property("awaitingChoice")
    d.advance()
    assert d.step == 1
    assert d.vela_ui.isChecked() and d.make_plan().vela_ui
    assert d.rounded_ui.isChecked() and d.make_plan().rounded_ui
    d.rounded_ui.setChecked(False)
    assert not d.make_plan().rounded_ui
    d.rounded_ui.setChecked(True)
    d.vela_ui.setChecked(False)
    assert not d.make_plan().vela_ui
    d.vela_ui.setChecked(True)
    # Rapid interrupted transitions and repeated layout updates must leave the
    # event loop responsive, including hide events on formerly invalid fields.
    ticks = []
    from PySide6.QtCore import QTimer

    heartbeat = QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(1))
    heartbeat.start()
    for index in range(12):
        d.advance()
        assert d.step == 2
        QTest.qWait(15)
        d.back.click()
        assert d.step == 1
        QTest.qWait(15)
    QTest.qWait(350)
    heartbeat.stop()
    assert len(ticks) >= 12 and not d.fade.isEnabled()
    d.advance()
    assert d.step == 2 and d.next.isEnabled() and d.next.property("awaitingChoice")
    d.advance()
    assert d.step == 2 and d.validation_glows[d.confirm].active
    assert not d.error.isVisible()
    if "--screenshots" in sys.argv:
        QTest.qWait(400)
        w.grab().save("/tmp/vela-reshade-review.png")
    d.confirm.setChecked(True)
    d.advance()
    assert d.step == 3
    for _ in range(100):
        QTest.qWait(20)
        if d.step != 3:
            break
    assert d.step == 4, d.error.text()
    assert (
        d.command.toPlainText() == 'WINEDLLOVERRIDES="dxgi=n,b" %command%'
        and (exe.parent / "dxgi.dll").exists()
    )
    # Existing installation routes to Configure instead of flagging the EXE.
    d.go(0)
    d.advance()
    assert d.step == 6 and d.mode == "configure" and not d.validation_glows[d.executable].active
    assert d.remove.isVisible() and "Vela-managed" in d.configure_info.text()
    assert d.editor.loaded and not d.next.isEnabled()
    from PySide6.QtWidgets import QAbstractSpinBox

    assert all(
        field.buttonSymbols() == QAbstractSpinBox.NoButtons for field in d.editor.controls.values()
    )
    d.editor.search.setText("rounding")
    QTest.qWait(20)
    visible = [keywords for card, keywords in d.editor.cards if not card.isHidden()]
    assert len(visible) >= 6 and all("rounding" in keywords for keywords in visible)
    assert not d.editor.dirty()
    d.editor.search.setText("no-such-reshade-setting")
    assert d.editor.empty.isVisible()
    d.editor.search.clear()

    before = (exe.parent / "ReShade.ini").read_bytes()
    d.editor.controls["alpha"].setValue(0.55)
    assert d.editor.dirty() and d.next.isEnabled() and d.next_glow.active
    assert (exe.parent / "ReShade.ini").read_bytes() == before
    d.next.click()
    assert not d.editor.dirty() and not d.next.isEnabled()
    assert "Alpha=0.55" in (exe.parent / "ReShade.ini").read_text()
    assert "EffectSearchPaths=" in (exe.parent / "ReShade.ini").read_text()

    if "--screenshots" in sys.argv:
        QTest.qWait(350)
        w.grab().save("/tmp/vela-reshade-configure.png")
    d.go(4)

    # Completion must leave a normal painted page, not a cached opacity layer
    # retaining the previous log viewport. Check minimum and restored sizes.
    for width, height in ((1060, 600), (1400, 780)):
        w.resize(width, height)
        QTest.qWait(350)
        assert not d.fade.isEnabled()
        assert d.command.isVisible() and d.ready_heading.isVisible() and not d.log.isVisible()
        assert d.command.width() <= d.stack.width()
    d.dismiss()
    QTest.qWait(350)
    d.open()
    QTest.qWait(450)
    assert d.step == 5 and not d.command.isVisible() and not d.log.isVisible()
    assert not d.executable.text() and d.games.currentIndex() == 0 and d.api.currentIndex() == 0
    d.api.setCurrentIndex(1)
    d.preset.setText("old.ini")
    for box in d.packages.values():
        box.setChecked(False)
    d.rounded_ui.setChecked(False)
    d.rounded_ui.setEnabled(False)
    d.vela_ui.setChecked(False)
    d.confirm.setChecked(True)
    d.complete_removal.setChecked(True)
    d.dismiss()
    QTest.qWait(350)
    d.open()
    QTest.qWait(450)
    assert d.api.currentIndex() == 0 and not d.preset.text()
    assert {key for key, box in d.packages.items() if box.isChecked()} == {"standard", "sweetfx"}
    assert d.rounded_ui.isChecked() and d.rounded_ui.isEnabled() and d.vela_ui.isChecked()
    assert not d.confirm.isChecked() and not d.complete_removal.isChecked()
    d.install_choice.click()
    d.executable.setText(str(exe))
    QTest.qWait(350)
    assert d.step == 6 and d.mode == "configure"
    d.back.click()
    assert d.step == 5
    d.configure_choice.click()
    assert d.step == 0
    assert not d.api.isVisible() and not d.api_heading.isVisible() and not d.api_hint.isVisible()
    assert d.panel.width() <= 720 and d.panel.height() <= 460
    d.advance()
    assert d.step == 6
    if "--screenshots" in sys.argv:
        folder = Path("/tmp/vela-reshade-ui")
        folder.mkdir(exist_ok=True)
        for step in (0, 1, 2, 4):
            d.go(step)
            QTest.qWait(350)
            w.grab().save(str(folder / f"step-{step}.png"))
        w.resize(1060, 600)
        d.go(0)
        QTest.qWait(350)
        w.grab().save(str(folder / "small.png"))
    (exe.parent / "VelaPreset.ini").write_text("modified preset")
    d.go(0)
    d.review_removal()
    assert d.removing and d.step == 2
    d.back.click()
    assert d.step == 6 and not d.removing
    d.review_removal()
    assert d.removing and d.step == 2
    d.complete_removal.setChecked(True)
    assert d.removal_files.isVisible() and "VelaPreset.ini" in d.removal_files.toPlainText()
    assert not d.confirm.isChecked()
    if "--screenshots" in sys.argv:
        d.advance()
        QTest.qWait(550)
        QTest.mouseMove(d.complete_removal, d.complete_removal.rect().center())
        QTest.qWait(350)
        w.grab().save("/tmp/vela-reshade-removal-options.png")
    d.confirm.setChecked(True)
    d.advance()
    assert d.step == 3
    for _ in range(100):
        QTest.qWait(20)
        if d.step != 3:
            break
    assert d.step == 4 and not (exe.parent / "dxgi.dll").exists(), d.error.text()
    assert d.panel.width() <= 720 and d.panel.height() <= 320
    assert not d.close_button.isVisible() and not d.another_game.isVisible() and d.next.isVisible()
    assert (
        not (exe.parent / "VelaPreset.ini").exists() and not (exe.parent / reshade.JOURNAL).exists()
    )
    assert (
        not d.command.isVisible()
        and not d.copy_launch.isVisible()
        and not d.game_directory.isVisible()
    )
    d.dismiss()
    QTest.qWait(350)
    assert w.preview.isVisible()
    # Closing during an installation also returns to step 1, without allowing
    # another operation or jumping to Ready when the background job completes.
    d.open()
    QTest.qWait(450)
    d.install_choice.click()
    d.executable.setText(str(exe))
    gate = threading.Event()

    def delayed_install(plan, report):
        if not gate.wait(5):
            raise RuntimeError("test gate timed out")
        return original_install(plan, report, download)

    with patch.object(reshade, "install", side_effect=delayed_install):
        d.advance()
        d.advance()
        d.confirm.setChecked(True)
        d.advance()
        assert d.operation_active
        d.dismiss()
        QTest.qWait(350)
        d.open()
        QTest.qWait(450)
        assert d.step == 5 and not d.install_choice.isEnabled()
        gate.set()
        for _ in range(100):
            QTest.qWait(20)
            if not d.operation_active:
                break
        assert not d.operation_active and d.step == 5 and d.install_choice.isEnabled()
    d.dismiss()
    QTest.qWait(350)
    # A failed scan must finish safely and permit a retry on the next opening.
    d.library_worker.deleteLater()
    d.library_worker = None
    with patch.object(reshade, "steam_games", side_effect=OSError("unreadable library")):
        d.open()
        QTest.qWait(450)
        assert d.library_worker is None and not d.busy()
        assert "scan failed" in d.library_status.text()
        assert "unreadable library" in d.library_status.toolTip()
        d.dismiss()
        QTest.qWait(350)
    d.open()
    QTest.qWait(450)
    assert d.library_worker is not None
    assert "0 installed Steam games" in d.library_status.text()
    d.dismiss()
    QTest.qWait(350)
    w.close()
print(
    "PASS: ReShade modal, validation, worker install, command preservation, removal and preview restoration"
)
