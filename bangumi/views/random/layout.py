"""随机页瀑布布局计算。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.platform import is_mobile

MAX_IMG_WIDTH = 225.0


def metrics(page: ft.Page) -> tuple[float, float, float, int, float]:
    """返回 (W, H, gap, cols, img_w)，按当前窗口实时计算。"""
    width = float(page.width or 1000)
    height = float(page.height or 800)
    w = max(120.0, width - 32.0)
    h = max(120.0, height - 56.0 - 32.0)
    gap = min(12.0, max(4.0, w * 0.008))
    mobile = is_mobile(page) or width < 760
    if mobile:
        # 移动端最多 3 张，尽量铺满整行。
        cols = 3
    else:        # 桌面端单张不小于 160px，最多 8 张。
        by_width = int((w + gap) // (160.0 + gap))
        cols = max(1, min(8, by_width))
    img_w = (
        (w - gap * (cols - 1)) / cols if cols else w
    )
    return w, h, gap, cols, img_w


def capacity(
    items: list[dict],
    cols: int,
    img_w: float,
    gap: float,
    height: float,
) -> int:
    """按实际行高计算可容纳的图片数；行条件为 used+gap+row_h <= H。"""
    ratios = [
        max(0.2, item.get("ratio", 480 / 679))
        for item in items
    ]
    rows = 0
    used = 0.0
    index = 0
    while index < len(ratios):
        row = ratios[index:index + cols]
        row_h = max(img_w / r for r in row)
        extra = gap if rows else 0.0
        if used + extra + row_h > height and rows >= 1:
            break
        used += extra + row_h
        rows += 1
        index += len(row)
    # 已排完现有图片后，按平均行高估算还能放几行。
    if ratios:
        avg = sum(img_w / r for r in ratios) / len(ratios)
        while used + gap + avg <= height:
            used += gap + avg
            rows += 1
    if rows <= 0:
        rows = 1
    return rows * cols
