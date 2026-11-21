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
    TITLE_HEIGHT,
)


def divider_gap(page_width: float) -> float:
    """竖线两侧间距：窄窗口 6px，宽窗口 12px。"""
    return 6.0 if page_width < 900 else 12.0


def button_width(
    page_width: float,
    max_label_px: float,
    measured: float | None = None,
) -> int:
    # 宽度只由左右列 + 竖线 + 两侧间距决定，骰子不占宽度。
    gap = divider_gap(page_width)
    usable = (
        page_width
        - PAGE_HORIZONTAL_PADDING * 2
        - SCROLLBAR_WIDTH * 2
        - DIVIDER_WIDTH
        - gap * 2
    )
    half = max(1.0, usable / 2)
    width = max(
        1.0,
        min(max_label_px + BUTTON_PADDING * 4, half),
    )
    # 有实测半列宽度时以实测为准，避免窗口变窄后右侧被裁。
    if measured is not None and measured > 0:
        width = min(width, float(measured))
    return int(max(1.0, width))


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
