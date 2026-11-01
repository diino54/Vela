"""Read and narrowly patch existing ReShade.ini files without touching presets.

Unknown keys, comments and line endings survive. Saving rejects stale snapshots
and symlinks; the ownership journal remains unchanged so edited INIs are preserved
by the default uninstaller.
"""

import configparser
import math
import os
import re
import stat
import tempfile
from pathlib import Path

from .reshade_theme import vela_theme

FIELDS = {
    "alpha": ("STYLE", "Alpha", 1.0, 0.1, 1.0),
    "font": ("STYLE", "FontSize", 13, 8, 32),
    "editor_font": ("STYLE", "EditorFontSize", 13, 8, 32),
    "rounding": ("STYLE", "WindowRounding", 0, 0, 24),
    "hdr": ("STYLE", "HdrOverlayBrightness", 203, 20, 400),
    "font_scale": ("STYLE", "FontScale", 1, 0.5, 3),
    "fps_scale": ("STYLE", "FPSScale", 1, 0.5, 3),
    "child_rounding": ("STYLE", "ChildRounding", 0, 0, 24),
    "popup_rounding": ("STYLE", "PopupRounding", 0, 0, 24),
    "frame_rounding": ("STYLE", "FrameRounding", 0, 0, 24),
    "grab_rounding": ("STYLE", "GrabRounding", 0, 0, 24),
    "scrollbar_rounding": ("STYLE", "ScrollbarRounding", 9, 0, 24),
    "tab_rounding": ("STYLE", "TabRounding", 5, 0, 24),
}


BOOL_FIELDS = {
    "fps": ("ShowFPS", False),
    "clock": ("ShowClock", False),
    "frametime": ("ShowFrameTime", False),
    "preset_name": ("ShowPresetName", False),
    "screenshot_message": ("ShowScreenshotMessage", True),
    "auto_save_preset": ("AutoSavePreset", True),
    "variable_tabs": ("VariableListUseTabs", False),
}


def parse(text):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_string(text)
    return config


def read_bytes(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("ReShade.ini must be a regular file.")
        data = stream.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("ReShade.ini exceeds the 2 MiB limit.")
    return data


def load(path):
    raw = read_bytes(path)
    config = parse(raw.decode("utf-8-sig"))
    values = {"theme": "current"}
    values.update(
        {
            name: config.get("OVERLAY", key, fallback="1" if default else "0") == "1"
            for name, (key, default) in BOOL_FIELDS.items()
        }
    )
    for name, (section, key, default, low, high) in FIELDS.items():
        value = float(config.get(section, key, fallback=str(default)))
        if not math.isfinite(value):
            raise ValueError(f"Invalid {key} value.")
        # Preserve readable existing values even outside the usual UI range.
        values[name] = value
    vela = parse(vela_theme())
    colors = ("Text", "WindowBg", "CheckMark")
    if config.get("STYLE", "StyleIndex", fallback="") == "4" and all(
        config.get("STYLE", key, fallback="") == vela.get("STYLE", key) for key in colors
    ):
        values["theme"] = "vela"
    elif config.get("STYLE", "StyleIndex", fallback="") == "2":
        values["theme"] = "default"
    return raw, values


def patch(text, changes):
    """Replace targeted keys in-place and append missing keys/sections."""
    newline = "\r\n" if "\r\n" in text else "\n"
    result = []
    pending = {section: dict(values) for section, values in changes.items()}
    section = None

    def finish():
        if section in pending:
            if result and not result[-1].endswith(("\n", "\r")):
                result[-1] += newline
            result.extend(f"{key}={value}{newline}" for key, value in pending.pop(section).items())

    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        header = re.match(r"\[([^]\r\n]+)\]", stripped)
        if header:
            finish()
            section = header.group(1)
        elif section in pending and "=" in line and not stripped.startswith((";", "#")):
            key = line.split("=", 1)[0].strip()
            if key in pending[section]:
                line = f"{key}={pending[section].pop(key)}{newline}"
        result.append(line)
    finish()
    for name, values in pending.items():
        if result and not result[-1].endswith(("\n", "\r")):
            result[-1] += newline
        result.append(f"{newline}[{name}]{newline}")
        result.extend(f"{key}={value}{newline}" for key, value in values.items())
    return "".join(result)


def save(path, original, values, baseline):
    path = Path(path)
    if read_bytes(path) != original:
        raise ValueError("ReShade.ini changed outside Vela. Reopen Configure before saving.")
    changes = {}
    for name, (section, key, default, low, high) in FIELDS.items():
        if values[name] == baseline[name]:
            continue
        value = float(values[name])
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        changes.setdefault(section, {})[key] = f"{value:g}"
    for name, (key, default) in BOOL_FIELDS.items():
        if values[name] != baseline[name]:
            changes.setdefault("OVERLAY", {})[key] = "1" if values[name] else "0"
    if values["theme"] != baseline["theme"]:
        if values["theme"] == "vela":
            theme = parse(vela_theme())
            numeric = {field[1] for field in FIELDS.values()} | {"EditorFontSize", "FontScale"}
            changes.setdefault("STYLE", {}).update(
                {key: value for key, value in theme["STYLE"].items() if key not in numeric}
            )
        elif values["theme"] == "default":
            changes.setdefault("STYLE", {}).update(StyleIndex="2", EditorStyleIndex="0")
        elif values["theme"] != "current":
            raise ValueError("Unknown theme.")
    text = original.decode("utf-8-sig")
    output = patch(text, changes).encode("utf-8")
    if original.startswith(b"\xef\xbb\xbf"):
        output = b"\xef\xbb\xbf" + output
    parse(output.decode("utf-8-sig"))
    fd, temporary = tempfile.mkstemp(prefix=".vela-ini-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(path.stat(follow_symlinks=False).st_mode))
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
        if read_bytes(path) != original:
            raise ValueError("ReShade.ini changed during save. Reopen Configure.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return load(path)
