import struct
import tempfile
import unittest
from pathlib import Path

from vela.steam_library import app_types, is_game


def cache(version, apps):
    keys = ["appinfo", "common", "type"]

    def key(name):
        return struct.pack("<I", keys.index(name)) if version == 29 else name.encode() + b"\0"

    records = b""
    for appid, kind in apps.items():
        payload = (
            b"\0"
            + key("appinfo")
            + b"\0"
            + key("common")
            + b"\1"
            + key("type")
            + kind.encode()
            + b"\0\x08\x08\x08"
        )
        metadata = bytes(40 if version == 27 else 60)
        records += struct.pack("<II", appid, len(metadata) + len(payload)) + metadata + payload
    records += bytes(4)
    header = struct.pack("<II", 0x07564400 + int(str(version), 16), 1)
    if version == 29:
        header += struct.pack("<Q", 16 + len(records))
        return (
            header
            + records
            + struct.pack("<I", len(keys))
            + b"".join(key.encode() + b"\0" for key in keys)
        )
    return header + records


class SteamLibraryTests(unittest.TestCase):
    def test_metadata_distinguishes_games_from_applications_and_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "appinfo.vdf"
            for version in (27, 28, 29):
                with self.subTest(version=version):
                    path.write_bytes(
                        cache(
                            version, {1: "Game", 2: "Application", 3: "Tool", 4: "Demo", 5: "DLC"}
                        )
                    )
                    kinds = app_types([path], {1, 2, 3, 4, 5})
                    self.assertEqual(
                        kinds, {1: "game", 2: "application", 3: "tool", 4: "demo", 5: "dlc"}
                    )
                    self.assertTrue(is_game("Proton Adventure", kinds[1]))
                    self.assertFalse(is_game("An unrelated editor", kinds[2]))
                    self.assertFalse(is_game("Steam Linux Runtime", kinds[3]))
                    self.assertTrue(is_game("Game demo", kinds[4]))
                    self.assertFalse(is_game("DLC", kinds[5]))
                    self.assertEqual(app_types([path], {2}), {2: "application"})

    def test_missing_corrupt_and_future_cache_fall_back_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "appinfo.vdf"
            self.assertEqual(app_types([path], {1}), {})
            for blob in (
                b"",
                b"corrupt",
                struct.pack("<II", 0x07564430, 1),
                cache(29, {1: "Game"})[:20],
            ):
                path.write_bytes(blob)
                self.assertEqual(app_types([path], {1}), {})
        for name in (
            "Lossless Scaling",
            "Steamworks Common Redistributables",
            "Steam Linux Runtime 4.0",
            "Proton Experimental",
        ):
            self.assertFalse(is_game(name))
        for name in (
            "HELLDIVERS™ 2",
            "Metro 2033 Redux",
            "Stardew Valley",
            "The Forever Winter",
            "The Runtime",
        ):
            self.assertTrue(is_game(name))
