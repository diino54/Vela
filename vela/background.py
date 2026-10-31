"""Shared frosted-grid texture for the OpenGL preview and tool panels."""
from functools import lru_cache
import math


@lru_cache(maxsize=4)
def frosted_pixels(width, height, strength=1., base=22):
    pixels = bytearray()
    vertical = [math.exp(-.5 * (abs((x + 10) % 42 - 21) / 15.) ** 2)
                for x in range(width)]
    for y in range(height):
        horizontal = math.exp(-.5 * (abs((y + 18) % 42 - 21) / 15.) ** 2)
        for x in range(width):
            distance = ((x / width - .53) / .7) ** 2 + ((y / height - .48) / .85) ** 2
            fade = max(0., 1 - distance) ** 2
            value = round(base + strength * (5 + 2 * max(horizontal, vertical[x])) * fade)
            pixels.extend((value, value, value + 1))
    return bytes(pixels)
