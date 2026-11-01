"""Read-only HDR report formatting. KScreen JSON is a desktop snapshot, not game telemetry.

Field contract: KDE/libkscreen src/configserializer.cpp (hdr, wcg,
sdr-brightness); absent fields must never imply disabled HDR.
"""

import json
import os
from pathlib import Path


def desktop_report(environ=None, drm=Path("/sys/class/drm")):
    env = os.environ if environ is None else environ
    lines = [
        "SESSION",
        f"Session: {env.get('XDG_SESSION_TYPE') or 'Unknown'}",
        f"Desktop: {env.get('XDG_CURRENT_DESKTOP') or 'Unknown'}",
        f"Desktop session: {env.get('XDG_SESSION_DESKTOP') or 'Unknown'}",
        "",
        "GPU DRIVERS",
    ]
    drivers = set()
    try:
        for card in drm.glob("card[0-9]*"):
            if "-" not in card.name and (card / "device/driver").is_symlink():
                drivers.add((card / "device/driver").resolve().name)
    except OSError:
        pass
    lines.append(", ".join(sorted(drivers)) or "Unavailable")
    return "\n".join(lines)


def toggle(value):
    return "Enabled" if value is True else "Disabled" if value is False else "Unknown"


def connected_outputs(raw):
    """Validate the snapshot once for both tiles and the copyable text report."""
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("outputs"), list):
        raise ValueError("No display snapshot in KScreen response")
    outputs = data["outputs"]
    if any(not isinstance(output, dict) for output in outputs):
        raise ValueError("Invalid display entry")
    return [output for output in outputs if output.get("connected") is True]


def kscreen_report(raw):
    lines = ["DESKTOP HDR · KScreen"]
    connected = connected_outputs(raw)
    if not connected:
        return "\n".join(lines + ["No connected displays reported. HDR state: Unknown."])
    for output in connected:
        lines += [
            "",
            str(output.get("name", "Unnamed display")),
            f"  Display: {toggle(output.get('enabled'))}",
            f"  HDR: {toggle(output.get('hdr'))}",
            f"  Wide color gamut: {toggle(output.get('wcg'))}",
        ]
        if isinstance(output.get("sdr-brightness"), (int, float)):
            lines.append(f"  SDR content brightness: {output['sdr-brightness']} nits")
        if isinstance(output.get("scale"), (int, float)):
            lines.append(f"  Scale: {output['scale']:g}×")
        modes = output.get("modes", [])
        if isinstance(modes, list):
            mode = next(
                (
                    mode
                    for mode in modes
                    if isinstance(mode, dict)
                    and mode.get("id") == output.get("currentModeId")
                    and "id" in mode
                ),
                {},
            )
            if mode:
                lines.append(f"  Mode: {mode.get('name', 'Unknown')}")
                rate = mode.get("refreshRate")
                if isinstance(rate, (int, float)):
                    lines.append(f"  Refresh rate: {rate:g} Hz")
    lines += ["", "Unknown means the backend did not expose that field."]
    return "\n".join(lines)


LIMITS = (
    "This report reads desktop state only. It does not verify a game’s HDR output, "
    "PQ/scRGB swapchain or display calibration. Vela MangoHud backdrop blur is currently disabled in HDR."
)


def display_metrics(output):
    """Stable tiles, including explicit missing values rather than hidden metrics."""
    modes = output.get("modes", [])
    mode = (
        next(
            (
                m
                for m in modes
                if isinstance(m, dict) and "id" in m and m["id"] == output.get("currentModeId")
            ),
            {},
        )
        if isinstance(modes, list)
        else {}
    )
    rate = mode.get("refreshRate")
    scale = output.get("scale")
    brightness = output.get("sdr-brightness")
    return [
        ("HDR Status", toggle(output.get("hdr")), "monitor"),
        ("Wide Color Gamut", toggle(output.get("wcg")), "color"),
        ("Display Status", toggle(output.get("enabled")), "monitor"),
        (
            "SDR Brightness",
            f"{brightness:g} nits" if type(brightness) in (int, float) else "Unknown",
            "sun",
        ),
        ("Display Mode", str(mode.get("name") or "Unknown"), "monitor"),
        ("Refresh Rate", f"{rate:.2f} Hz" if type(rate) in (int, float) else "Unknown", "refresh"),
        ("Scale", f"{scale:g}×" if type(scale) in (int, float) else "Unknown", "scale"),
    ]
