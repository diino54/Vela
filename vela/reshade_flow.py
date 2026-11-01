"""Stable ReShade page IDs and page-specific layout limits."""

from enum import IntEnum


class Page(IntEnum):
    GAME = 0
    EFFECTS = 1
    REVIEW = 2
    INSTALL = 3
    READY = 4
    HOME = 5
    CONFIGURE = 6


def panel_size(page, mode, removed=False):
    if page == Page.READY and removed:
        return 720, 320
    if page == Page.HOME:
        return 720, 380
    if page == Page.CONFIGURE:
        return 820, 560
    if page == Page.GAME and mode == "configure":
        return 720, 460
    return 900, 680
