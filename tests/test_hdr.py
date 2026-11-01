"""HDR snapshots distinguish disabled, missing and failed readings."""

import unittest
from pathlib import Path

from vela.hdr import desktop_report, kscreen_report


class HdrTests(unittest.TestCase):
    def test_enabled_disabled_and_missing(self):
        import json

        report = kscreen_report(
            json.dumps(
                {
                    "outputs": [
                        {
                            "name": "DP-1",
                            "connected": True,
                            "enabled": True,
                            "hdr": True,
                            "wcg": True,
                            "sdr-brightness": 203,
                            "currentModeId": "1",
                            "modes": [{"id": "1", "name": "2560x1440", "refreshRate": 144}],
                        },
                        {"name": "HDMI-1", "connected": True, "hdr": False},
                        {"name": "DP-2", "connected": True},
                        {"name": "DP-3", "connected": False, "hdr": True},
                    ]
                }
            )
        )
        self.assertIn("HDR: Enabled", report)
        self.assertIn("HDR: Disabled", report)
        self.assertIn("HDR: Unknown", report)
        self.assertIn("203 nits", report)
        self.assertIn("144 Hz", report)
        self.assertNotIn("DP-3", report)

    def test_invalid_and_empty(self):
        for raw in ("null", "{}", '{"outputs":{}}', '{"outputs":[null]}', "bad"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                kscreen_report(raw)
        self.assertIn("Unknown", kscreen_report('{"outputs":[]}'))
        self.assertIn("Session: Unknown", desktop_report({}, Path("/nonexistent-vela-test")))
