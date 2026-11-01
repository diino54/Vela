"""Settings edits preserve unknown game/preset data and reject unsafe/stale saves."""

import tempfile
import unittest
from pathlib import Path

from vela import reshade_config as cfg
from vela.reshade_theme import vela_theme


class ConfigTests(unittest.TestCase):
    def test_narrow_save_preserves_comments_paths_and_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ReShade.ini"
            original = (
                "; leave me\r\n[GENERAL]\r\nPresetPath=.\\MyPreset.ini\r\nUnknown=unchanged\r\n"
                + vela_theme().replace("\n", "\r\n")
            ).encode()
            path.write_bytes(original)
            raw, values = cfg.load(path)
            edited = dict(values, alpha=0.55, fps=True)
            cfg.save(path, raw, edited, values)
            saved = path.read_bytes()
            self.assertIn(b"; leave me\r\n", saved)
            self.assertIn(b"PresetPath=.\\MyPreset.ini\r\nUnknown=unchanged\r\n", saved)
            self.assertIn(b"Alpha=0.55\r\n", saved)
            self.assertIn(b"ShowFPS=1\r\n", saved)
            self.assertNotIn(b"\n", saved.replace(b"\r\n", b""))
            self.assertEqual(cfg.load(path)[1]["font"], 13)

    def test_commented_section_headers_remain_editable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ReShade.ini"
            path.write_text(
                "[STYLE] ; custom style\nAlpha=0.7\nUnknown=keep\n[OVERLAY] # overlay\nShowFPS=0\n"
            )
            raw, values = cfg.load(path)
            cfg.save(path, raw, dict(values, alpha=0.5, fps=True), values)
            saved = path.read_text()
            self.assertIn("[STYLE] ; custom style", saved)
            self.assertIn("[OVERLAY] # overlay", saved)
            self.assertIn("Unknown=keep", saved)
            self.assertEqual(saved.count("[STYLE]"), 1)
            self.assertEqual(cfg.load(path)[1]["alpha"], 0.5)
            self.assertTrue(cfg.load(path)[1]["fps"])

    def test_native_visual_options_use_the_vela_section(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ReShade.ini"
            path.write_text(vela_theme())
            raw, values = cfg.load(path)
            cfg.save(
                path,
                raw,
                dict(values, blur=8, blur_quality=2, animations=False, animation_duration=0.4),
                values,
            )
            config = cfg.parse(path.read_text())
            self.assertEqual(config["VELA"]["BackgroundBlur"], "8")
            self.assertEqual(config["VELA"]["BlurQuality"], "2")
            self.assertEqual(config["VELA"]["Animations"], "0")
            self.assertEqual(config["VELA"]["AnimationDuration"], "0.4")
            self.assertEqual(config["OVERLAY"]["ShowFPS"], "0")
            self.assertEqual(config["STYLE"]["Alpha"], "0.7")
            loaded = cfg.load(path)[1]
            self.assertFalse(loaded["animations"])
            self.assertEqual(loaded["blur_quality"], 2)

    def test_extended_options_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ReShade.ini"
            path.write_text(vela_theme())
            raw, values = cfg.load(path)
            cfg.save(
                path,
                raw,
                dict(values, clock=True, auto_save_preset=False, font_scale=1.25, frame_rounding=4),
                values,
            )
            loaded = cfg.load(path)[1]
            self.assertTrue(loaded["clock"])
            self.assertFalse(loaded["auto_save_preset"])
            self.assertEqual(loaded["font_scale"], 1.25)
            self.assertEqual(loaded["frame_rounding"], 4)

    def test_stale_symlink_and_invalid_values_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ReShade.ini"
            path.write_text(vela_theme())
            raw, values = cfg.load(path)
            path.write_text(vela_theme() + "\n; game wrote this\n")
            changed = path.read_bytes()
            with self.assertRaises(ValueError):
                cfg.save(path, raw, dict(values, alpha=0.5), values)
            self.assertEqual(path.read_bytes(), changed)
            raw, values = cfg.load(path)
            with self.assertRaises(ValueError):
                cfg.save(path, raw, dict(values, alpha=5), values)
            link = Path(directory) / "linked.ini"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                cfg.load(link)

    def test_theme_only_keeps_font_alpha_and_preset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ReShade.ini"
            path.write_text(
                "[GENERAL]\nPresetPath=custom.ini\n[STYLE]\nAlpha=0.9\nFontSize=19\nEditorFontSize=16\nWindowRounding=3\nHdrOverlayBrightness=150\n"
            )
            raw, values = cfg.load(path)
            cfg.save(path, raw, dict(values, theme="vela"), values)
            parsed = cfg.parse(path.read_text())
            self.assertEqual(parsed["STYLE"]["Alpha"], "0.9")
            self.assertEqual(parsed["STYLE"]["FontSize"], "19")
            self.assertEqual(parsed["STYLE"]["WindowRounding"], "3")
            self.assertEqual(parsed["GENERAL"]["PresetPath"], "custom.ini")
            self.assertEqual(parsed["STYLE"]["StyleIndex"], "4")
            raw, values = cfg.load(path)
            cfg.save(path, raw, dict(values, theme="default"), values)
            self.assertEqual(cfg.parse(path.read_text())["STYLE"]["StyleIndex"], "2")
