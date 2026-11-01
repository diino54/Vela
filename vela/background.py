"""Shared frosted-grid texture for the OpenGL preview and tool panels."""

import math
from functools import lru_cache

# Preview-only choices. These are not MangoHud appearance/configuration keys.
PREVIEW_BACKGROUNDS = (
    ("Frosted scene", "frosted"),
    ("Daylight · aerial view", "daylight"),
    ("Night · aerial view", "night"),
)


@lru_cache(maxsize=4)
def frosted_pixels(width, height, strength=1.0, base=22):
    pixels = bytearray()
    vertical = [math.exp(-0.5 * (abs((x + 10) % 42 - 21) / 15.0) ** 2) for x in range(width)]
    for y in range(height):
        horizontal = math.exp(-0.5 * (abs((y + 18) % 42 - 21) / 15.0) ** 2)
        for x in range(width):
            distance = ((x / width - 0.53) / 0.7) ** 2 + ((y / height - 0.48) / 0.85) ** 2
            fade = max(0.0, 1 - distance) ** 2
            value = round(base + strength * (5 + 2 * max(horizontal, vertical[x])) * fade)
            pixels.extend((value, value, value + 1))
    return bytes(pixels)
