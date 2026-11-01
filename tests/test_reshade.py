"""ReShade installation tests use tiny synthetic PEs and temporary game folders."""

import configparser
import json
import os
import struct
import tempfile
import unittest
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from vela import reshade


def pe(bits=64):
    blob = bytearray(160)
    blob[:2] = b"MZ"
    struct.pack_into("<I", blob, 0x3C, 128)
    blob[128:132] = b"PE\0\0"
    struct.pack_into("<H", blob, 132, 0x8664 if bits == 64 else 0x14C)
    return bytes(blob)


def zipped(files):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


def download(url):
    if url == reshade.HOME:
        return b'<a href="/downloads/ReShade_Setup_6.8.0.exe">Download</a>'
    if url.endswith(".exe"):
        return b"MZ" + zipped({"ReShade32.dll": pe(32), "ReShade64.dll": pe(64)})
    return zipped(
        {
            "pack/Shaders/Test.fx": b"effect",
            "pack/Shaders/Include.fxh": b"include",
            "pack/LICENSE": b"license",
        }
    )


class ReShadeTests(unittest.TestCase):
    def test_pe_reader_rejects_special_files_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / "blocked.exe"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, "regular Windows executable"):
                reshade.pe_bits(fifo)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.exe = self.folder / "Game.exe"
        self.exe.write_bytes(pe())
        self.plan = reshade.Plan(self.exe, "dxgi", ("standard", "quint"))

    def test_install_and_preserve_user_changes_on_removal(self):
        manifest = reshade.install(self.plan, download=download)
        self.assertEqual(manifest["version"], "6.8.0")
        self.assertEqual((self.folder / "dxgi.dll").read_bytes(), pe())
        self.assertIn("quint", (self.folder / "ReShade.ini").read_text())
        (self.folder / "VelaPreset.ini").write_text("Techniques=Custom")
        (self.folder / "other-mod.dll").write_bytes(b"other")
        preserved = reshade.uninstall(self.exe)
        self.assertEqual(preserved, ["VelaPreset.ini"])
        self.assertFalse((self.folder / "dxgi.dll").exists())
        self.assertFalse((self.folder / reshade.SHADERS).exists())
        self.assertEqual((self.folder / "other-mod.dll").read_bytes(), b"other")
        self.assertEqual((self.folder / "VelaPreset.ini").read_text(), "Techniques=Custom")

    def test_complete_removal_includes_modified_and_added_files(self):
        reshade.install(self.plan, download=download)
        (self.folder / "VelaPreset.ini").write_text("user changes")
        (self.folder / "ReShade.ini").write_text("edited config")
        extra = self.folder / reshade.SHADERS / "custom"
        extra.mkdir()
        (extra / "New.fx").write_text("custom shader")
        (self.folder / "ReShade.log").write_text("runtime log")
        (self.folder / "other-mod.dll").write_bytes(b"keep")
        names = reshade.complete_removal_files(self.exe)
        self.assertIn("VelaPreset.ini", names)
        self.assertIn(reshade.SHADERS + "/custom/New.fx", names)
        self.assertIn("ReShade.log", names)
        self.assertEqual(reshade.uninstall(self.exe, complete=True), [])
        self.assertEqual({p.name for p in self.folder.iterdir()}, {"Game.exe", "other-mod.dll"})

    def test_complete_removal_rejects_shader_symlinks_before_deletion(self):
        reshade.install(self.plan, download=download)
        outside = self.folder / "unrelated"
        outside.write_text("keep")
        link = self.folder / reshade.SHADERS / "outside"
        link.symlink_to(outside)
        with self.assertRaises(ValueError):
            reshade.uninstall(self.exe, complete=True)
        self.assertTrue((self.folder / "dxgi.dll").exists())
        self.assertEqual(outside.read_text(), "keep")

    def test_rounded_runtime_uses_local_build_and_preserves_official_choice(self):
        plan = replace(self.plan, rounded_ui=True, vela_ui=False)
        requested = []

        def only_shaders(url):
            requested.append(url)
            self.assertIn("codeload.github.com", url)
            return download(url)

        with patch.object(reshade, "rounded_runtime", return_value=("6.8.0", pe())) as local:
            manifest = reshade.install(plan, download=only_shaders)
        local.assert_called_once_with(64)
        self.assertEqual(manifest["runtime"], "vela-rounded")
        self.assertIn("WindowRounding=12", (self.folder / "ReShade.ini").read_text())
        self.assertNotIn("FontSize=", (self.folder / "ReShade.ini").read_text())
        self.assertEqual(len(requested), 2)

    def test_local_runtime_checks_hash_and_architecture(self):
        directory = self.folder / "native/reshade"
        directory.mkdir(parents=True)
        dll = directory / "ReShade64.dll"
        dll.write_bytes(pe())
        (directory / "BUILD.json").write_text(
            json.dumps({"version": "6.8.0", "sha256": {"64": reshade.digest(pe())}})
        )
        with patch.object(reshade, "__file__", str(self.folder / "reshade.py")):
            self.assertTrue(reshade.rounded_available(64))
            self.assertEqual(reshade.rounded_runtime(64), ("6.8.0", pe()))
            dll.write_bytes(pe(32))
            with self.assertRaises(ValueError):
                reshade.rounded_runtime(64)
            dll.write_bytes(pe() + b"changed")
            with self.assertRaises(ValueError):
                reshade.rounded_runtime(64)

    def test_optional_vela_theme_is_written_to_the_actual_runtime_config(self):
        reshade.install(self.plan, download=download)
        config = configparser.ConfigParser()
        config.read(self.folder / "ReShade.ini")
        self.assertEqual(config["STYLE"]["StyleIndex"], "4")
        self.assertEqual(config["STYLE"]["FontSize"], "13")
        self.assertEqual(config["STYLE"]["EditorFontSize"], "13")
        self.assertEqual(config["STYLE"]["HdrOverlayBrightness"], "400")
        self.assertEqual(config["OVERLAY"]["ShowFPS"], "0")
        self.assertEqual(config["STYLE"]["WindowRounding"], "12")
        self.assertEqual(config["STYLE"]["FrameRounding"], "7")
        self.assertEqual(config["STYLE"]["Alpha"], "0.7")
        self.assertEqual(config["STYLE"]["Text"], "1.000000,1.000000,1.000000,1.000000")
        reshade.uninstall(self.exe)
        reshade.install(replace(self.plan, vela_ui=False), download=download)
        config = configparser.ConfigParser()
        config.read(self.folder / "ReShade.ini")
        self.assertNotIn("STYLE", config)
        self.assertNotIn("OVERLAY", config)
        self.assertIn("EffectSearchPaths", config["GENERAL"])

    def test_existing_mods_and_symlinks_not_overwritten(self):
        target = self.folder / "DXGI.dll"
        target.write_bytes(b"existing mod")
        with self.assertRaisesRegex(ValueError, "Existing files"):
            reshade.install(self.plan, download=download)
        self.assertEqual(target.read_bytes(), b"existing mod")
        target.unlink()
        target = self.folder / "dxgi.dll"
        target.symlink_to(self.folder / "missing")
        with self.assertRaises(ValueError):
            reshade.install(self.plan, download=download)
        self.assertTrue(target.is_symlink())

    def test_exclusive_publication_rolls_back_on_failure(self):
        real_link = reshade.os.link
        count = 0

        def failing_link(source, target):
            nonlocal count
            count += 1
            if count == 4:
                raise OSError("disk full")
            real_link(source, target)

        with patch.object(reshade.os, "link", side_effect=failing_link):
            with self.assertRaisesRegex(OSError, "disk full"):
                reshade.install(self.plan, download=download)
        self.assertEqual(list(self.folder.iterdir()), [self.exe])

    def test_download_failure_writes_nothing(self):
        def failed(url):
            if "codeload" in url:
                raise OSError("offline")
            return download(url)

        with self.assertRaises(OSError):
            reshade.install(self.plan, download=failed)
        self.assertEqual(list(self.folder.iterdir()), [self.exe])

    def test_architecture_and_archive_validation(self):
        self.assertEqual(reshade.pe_bits(self.exe), 64)
        self.exe.write_bytes(pe(32))
        self.assertEqual(reshade.pe_bits(self.exe), 32)
        with self.assertRaises(ValueError):
            reshade.runtime_dll(zipped({"ReShade64.dll": pe(32)}), 64)
        with self.assertRaises(ValueError):
            reshade.package_files(zipped({"pack/../../bad.fx": b"bad"}), "standard")
        with self.assertRaises(ValueError):
            reshade.package_files(zipped({"pack/README": b"empty"}), "standard")

    def test_uninstall_rejects_outside_paths(self):
        reshade.install(self.plan, download=download)
        journal = self.folder / reshade.JOURNAL
        manifest = json.loads(journal.read_text())
        manifest["files"]["../outside"] = reshade.digest(b"anything")
        journal.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            reshade.uninstall(self.exe)
        self.assertTrue((self.folder / "dxgi.dll").exists())

    def test_launch_command_preserves_other_options(self):
        options = "PROTON_ENABLE_WAYLAND=1 gamemoderun vela-mangohud %command%"
        self.assertEqual(
            reshade.launch_options("dxgi", options), 'WINEDLLOVERRIDES="dxgi=n,b" ' + options
        )
        self.assertEqual(
            reshade.launch_options("dxgi", 'WINEDLLOVERRIDES="dinput8=n,b;dxgi=b" %command%'),
            'WINEDLLOVERRIDES="dinput8=n,b;dxgi=n,b" %command%',
        )
        with self.assertRaises(ValueError):
            reshade.launch_options("dxgi", "missing command")


if __name__ == "__main__":
    unittest.main()
