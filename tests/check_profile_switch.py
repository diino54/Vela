"""Offline profile/global switch regression; all files and preferences are temporary."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vela import mangohud
from vela.preview import Preview
from vela.profile_switch import find_identity
from vela.ui import Window

app = QApplication([])
with (
    tempfile.TemporaryDirectory() as temp,
    patch.object(Preview, "start"),
    patch.object(mangohud, "discover", return_value=[]),
):
    d = Path(temp)
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, temp)
    global_path = d / "MangoHud.conf"
    global_path.write_text("font_size=22\n")
    a = mangohud.Session(101, "a", "Stalker2.exe", d, global_path, True)
    b = mangohud.Session(202, "b", "OtherGame.exe", d, None, False)
    a.profile.write_text("font_size=24\ncustom_option=keep\n")
    b.profile.write_text("font_size=26\n")
    w = Window()
    w.timer.stop()
    w.show()
    w.config_path.setText(str(global_path))
    w.change_global_config()
    assert w.preview_source.full_text == "Preview - Global configuration"
    w.sessions = [a, b]
    w.process.blockSignals(True)
    w.process.addItem(a.name, a.identity)
    w.process.addItem(b.name, b.identity)
    w.process.setCurrentIndex(0)
    w.process.blockSignals(False)
    w.selection_changed()
    assert (
        w.preview.global_config == a.profile and w.preview_source.full_text == "Preview - Stalker2"
    )

    def switch(index):
        w.process.setCurrentIndex(index)
        app.processEvents()

    def edit(size):
        w.appearance_controls["font_size"].setValue(size)
        app.processEvents()

    edit(30)
    switch(1)
    assert w.profile_switch.pending and w.process.currentData() == a.identity
    assert w.appearance_controls["font_size"].value() == 30 and w.status.actions is not None
    w.status.dismiss()
    QTest.qWait(500)
    assert w.profile_switch.pending is None and w.process.currentData() == a.identity
    assert w.appearance_controls["font_size"].value() == 30
    switch(1)
    w.profile_switch.resolve(False)
    assert w.process.currentData() == b.identity and w.preview.global_config == b.profile
    assert mangohud.appearance_values(a.profile.read_text())["font_size"] == 24
    edit(32)
    switch(0)
    w.profile_switch.resolve(True)
    assert (
        w.process.currentData() == a.identity and w.preview_source.full_text == "Preview - Stalker2"
    )
    assert mangohud.appearance_values(b.profile.read_text())["font_size"] == 32
    edit(35)
    switch(1)
    with patch.object(mangohud, "save_appearance", side_effect=OSError("test failure")):
        w.profile_switch.resolve(True)
    assert (
        w.profile_switch.pending
        and w.process.currentData() == a.identity
        and w.appearance_controls["font_size"].value() == 35
        and "Cannot save" in w.status.detail.text()
    )
    w.profile_switch.resolve(True)
    assert (
        w.process.currentData() == b.identity
        and mangohud.appearance_values(a.profile.read_text())["font_size"] == 35
    )
    # Switch from global buffer as well, including files that do not have game profiles.
    w.process.blockSignals(True)
    w.process.setCurrentIndex(-1)
    w.process.blockSignals(False)
    w.selection_changed(force=True)
    assert w.preview_source.full_text == "Preview - Global configuration"
    edit(28)
    switch(0)
    assert w.profile_switch.pending
    w.profile_switch.resolve(True)
    assert mangohud.appearance_values(global_path.read_text())["font_size"] == 28
    edit(37)
    w.save_configuration("profile", a.identity)
    switch(1)
    assert w.profile_switch.pending is None
    edit(38)
    switch(0)
    assert w.profile_switch.pending
    # Polling rebuilds the combo with equal-but-distinct tuple objects.
    w.process.blockSignals(True)
    w.process.clear()
    w.process.addItem(a.name, a.identity)
    w.process.addItem(b.name, b.identity)
    w.process.setCurrentIndex(1)
    w.process.blockSignals(False)
    w.process.blockSignals(True)
    w.process.removeItem(find_identity(w.process, a.identity))
    w.process.blockSignals(False)
    w.profile_switch.resolve(False)
    assert w.profile_switch.pending and w.appearance_controls["font_size"].value() == 38
    w.status.hide_immediately(force=True)
    assert w.profile_switch.pending is None
    assert "custom_option=keep" in a.profile.read_text()
    w.preview.shutdown()
    w.close()
    print(
        "Profile/global headers, cancel, discard, save, failed-save retention and correct original file passed"
    )
