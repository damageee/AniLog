"""虚拟列表滚动窗口的纯数学计算。"""

from __future__ import annotations

import math


def max_scroll_offset(
    count: int,
    step: float,
    list_height: float,
    gap: float = 0.0,
) -> float:
    content_height = max(
        list_height,
        count * step - gap,
    )
    return max(0.0, content_height - list_height)


def clamp_scroll(pixels: float, max_offset: float) -> float:
    if not math.isfinite(pixels):
        return 0.0
    return max(0.0, min(max_offset, pixels))


def window_size(
    list_height: float,
    step: float,
    extra: int = 4,
) -> int:
    visible_rows = math.ceil(list_height / step) + 1
    return visible_rows + extra


def window_bounds(
    pixels: float,
    count: int,
    window: int,
    step: float,
    overscan: int = 2,
) -> tuple[int, int]:
    first = int(pixels // step) - overscan
    first = max(0, min(first, max(0, count - window)))
    last = min(count - 1, first + window - 1)
    return first, last
