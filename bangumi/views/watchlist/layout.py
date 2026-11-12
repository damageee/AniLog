"""已追页面的布局尺寸计算。"""

from __future__ import annotations

from bangumi.views.watchlist.constants import (
    ANDROID_BUTTON_AREA_HEIGHT,
    BUTTON_PADDING,
    BUTTON_ROW_HEIGHT,
    DIVIDER_WIDTH,
    HALF_GAP,
    HALF_HEIGHT,
    PAGE_HORIZONTAL_PADDING,
    SCROLLBAR_WIDTH,
    SIDE_GAP,
    TITLE_HEIGHT,
)


def button_width(page_width: float, max_label_px: float) -> int:
    usable = (
        page_width
        - PAGE_HORIZONTAL_PADDING * 2
        - DIVIDER_WIDTH
        - SCROLLBAR_WIDTH * 2
        - SIDE_GAP * 2
    )
    half = max(1.0, usable / 2)
    return int(
        max(
            1.0,
            min(max_label_px + BUTTON_PADDING * 4, half),
        )
    )


def list_height(android: bool) -> float:
    button_area_height = (
        ANDROID_BUTTON_AREA_HEIGHT
        if android
        else BUTTON_ROW_HEIGHT
    )
    return (
        HALF_HEIGHT
        - TITLE_HEIGHT
        - HALF_GAP * 2
        - button_area_height
    )
