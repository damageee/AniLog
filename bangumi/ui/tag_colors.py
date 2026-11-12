"""确定性的逐标签配色。"""

from __future__ import annotations

import colorsys
import re

from bangumi.data.watched_data import Record, split_tags

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
FALLBACK_TAG_COLOR = "#CFD8DC"
TAG_COLOR_VERSION = 1

PALETTE: tuple[str, ...] = (
    "#4DB6AC",
    "#4FC3F7",
    "#64B5F6",
    "#7986CB",
    "#8C9EFF",
    "#9575CD",
    "#BA68C8",
    "#B388FF",
    "#F06292",
    "#FF80AB",
    "#EF5350",
    "#FF8A80",
    "#FF8A65",
    "#FFB74D",
    "#FFD54F",
    "#FFCA28",
    "#9CCC65",
    "#AED581",
    "#81C784",
    "#66BB6A",
    "#4DD0E1",
    "#26C6DA",
    "#A1887F",
    "#90A4AE",
)


def is_valid_color(value: object) -> bool:
    """``#RRGGBB`` 颜色字符串返回 True。"""
    return isinstance(value, str) and _COLOR_RE.match(value) is not None


def relative_luminance(color: str) -> float:
    """返回 ``#RRGGBB`` 颜色的 WCAG 相对亮度。"""
    if not is_valid_color(color):
        return 0.0

    def channel(value: int) -> float:
        normalized = value / 255.0
        if normalized <= 0.04045:
            return normalized / 12.92
        return ((normalized + 0.055) / 1.055) ** 2.4

    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return (
        0.2126 * channel(red)
        + 0.7152 * channel(green)
        + 0.0722 * channel(blue)
    )


def _hsl_to_hex(
    hue: float,
    saturation: float,
    lightness: float,
) -> str:
    red, green, blue = colorsys.hls_to_rgb(
        hue / 360.0,
        lightness,
        saturation,
    )
    return "#{:02X}{:02X}{:02X}".format(
        int(round(red * 255)),
        int(round(green * 255)),
        int(round(blue * 255)),
    )


def assign_color(used: set[str] | dict[str, str]) -> str:
    """选取第一个未使用的调色板颜色，然后生成唯一的 HSL 色相。"""
    used_upper = {str(color).upper() for color in used}
    for color in PALETTE:
        if color.upper() not in used_upper:
            return color

    hue = 0.0
    while True:
        hue = (hue + 137.508) % 360
        color = _hsl_to_hex(hue, 0.62, 0.64)
        if color.upper() not in used_upper:
            return color


def sync_tag_colors(records: list[Record], preferences) -> bool:
    """保持 ``preferences.tag_colors`` 与当前标签集合一致。"""
    changed = False
    if (
        getattr(preferences, "tag_color_version", 0)
        != TAG_COLOR_VERSION
    ):
        preferences.tag_colors.clear()
        preferences.tag_color_version = TAG_COLOR_VERSION
        changed = True

    tags: list[str] = []
    seen: set[str] = set()
    for record in records:
        for tag in split_tags(record.get("tag", "")):
            if tag not in seen:
                seen.add(tag)
                tags.append(tag)

    current = set(tags)
    colors: dict[str, str] = preferences.tag_colors

    for tag in list(colors):
        if tag not in current:
            del colors[tag]
            changed = True

    used: dict[str, str] = {}
    resolved: dict[str, str] = {}

    # 先保留已有的有效颜色，使新颜色无法抢占它们。
    for tag in tags:
        color = colors.get(tag)
        if not is_valid_color(color):
            continue
        color = color.upper()
        if color in used:
            continue
        used[color] = tag
        resolved[tag] = color

    for tag in tags:
        color = resolved.get(tag)
        if color is None:
            color = assign_color(set(used))
            used[color] = tag
            changed = True
        if colors.get(tag) != color:
            colors[tag] = color
            changed = True

    if changed:
        preferences.save()
    return changed
