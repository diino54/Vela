"""Validate only owned native-harness exports: blur, fade, bounds and HDR values."""

import argparse
import math
from array import array
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--blur", type=Path, required=True)
parser.add_argument("--no-blur", type=Path, required=True)
parser.add_argument("--hdr", type=Path, action="append", default=[])
args = parser.parse_args()
roi = (160, 360, 285, 540)
outside = (550, 120, 850, 550)


def delta(a, b, region):
    return sum(ImageStat.Stat(ImageChops.difference(a, b).crop(region)).mean) / 3


def validate(folder):
    images = {
        frame: Image.open(folder / f"visual-{frame}.ppm")
        for frame in (149, 153, 160, 180, 302, 310, 330)
    }
    before, opened, closed = images[149], images[180], images[330]
    assert delta(before, opened, roi) > 1, "Overlay was not visible"
    assert delta(before, opened, outside) == 0, "Image outside the panel changed"
    assert delta(before, closed, roi) == 0, "Closed menu left pixels behind"
    # PQ/scRGB display conversion makes average brightness non-monotonic.
    # An intermediate image must differ from both endpoints, not lie between
    # their encoded means. Closing time is wall-clock based, not frame-count based.
    assert delta(before, images[153], roi) > 0 and delta(opened, images[153], roi) > 0, (
        "No intermediate opening frame"
    )
    assert any(
        delta(before, images[f], roi) > 0 and delta(opened, images[f], roi) > 0 for f in (302, 310)
    ), "No intermediate closing frame"
    for frame in (149, 180, 330):
        with (folder / f"visual-{frame}.rgb32f").open("rb") as stream:
            width, height = map(int, stream.readline().split())
            assert 0 < width <= 8192 and 0 < height <= 8192
            pixels = array("f")
            pixels.frombytes(stream.read())
        assert len(pixels) == width * height * 3
        assert all(math.isfinite(value) for value in pixels), "Non-finite GPU output"
    print(
        "PASS:",
        folder.name,
        "fade checkpoints, unchanged outside, no closed-menu residue, finite pixels",
    )
    return sum(ImageStat.Stat(opened.crop(roi)).stddev) / 3


blur = validate(args.blur)
plain = validate(args.no_blur)
assert blur < plain * 0.25, (blur, plain)
print(f"PASS: checker contrast {plain:.3f} → {blur:.3f} with GPU blur")
for folder in args.hdr:
    validate(folder)
