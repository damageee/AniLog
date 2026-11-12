"""测量渲染文本宽度，用于表格列宽计算。"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from bangumi.core.paths import assets_directory

try:
    from PIL import ImageFont
except ImportError:  # pragma: no cover - fallback for unusual builds
    ImageFont = None

TABLE_FONT_SIZE = 14
_FONT_FILES = {
    False: ("consola.ttf", "simsun_proc.ttf"),
    True: ("consolab.ttf", "simsun_proc.ttf"),
}


def text_width(
    value: str,
    *,
    bold: bool = False,
    size: int = TABLE_FONT_SIZE,
) -> int:
    """返回 `value` 以逻辑像素计的渲染宽度。"""
    return _measure_text(value, bold=bold, size=size)


def truncate_display(
    value: str,
    limit: int = 100,
    suffix: str = "...",
) -> str:
    """将 ``value`` 截断到 ``limit`` 个显示单元，宽字符按 2 计。"""
    text = (
        str(value or "")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    width = 0
    for index, char in enumerate(text):
        char_width = 2 if _is_wide(char) else 1
        if width + char_width > limit:
            return text[:index] + suffix
        width += char_width
    return text


@lru_cache(maxsize=16384)
def _measure_text(
    value: str,
    *,
    bold: bool,
    size: int,
) -> int:
    text = (
        value.replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", "    ")
    )
    if not text:
        return 0

    fonts = _fonts(bold, size)
    if fonts is None:
        return _fallback_width(text, bold=bold, size=size)

    width = 0.0
    run: list[str] = []
    run_is_ascii = text[0].isascii()

    for char in text:
        is_ascii = char.isascii()
        if is_ascii != run_is_ascii:
            width += _run_width(fonts, run, run_is_ascii)
            run = []
            run_is_ascii = is_ascii
        run.append(char)

    width += _run_width(fonts, run, run_is_ascii)
    return math.ceil(width)


def _run_width(
    fonts: tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont],
    run: list[str],
    is_ascii: bool,
) -> float:
    if not run:
        return 0.0
    font = fonts[0] if is_ascii else fonts[1]
    return font.getlength("".join(run))


@lru_cache(maxsize=None)
def _fonts(
    bold: bool,
    size: int,
) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont] | None:
    if ImageFont is None:
        return None

    ascii_name, wide_name = _FONT_FILES[bold]
    ascii_font = _load_font(ascii_name, size)
    wide_font = _load_font(wide_name, size)
    if ascii_font is None or wide_font is None:
        return None
    return ascii_font, wide_font


@lru_cache(maxsize=None)
def _load_font(name: str, size: int):
    path = _assets_directory() / "fonts" / name
    try:
        return ImageFont.truetype(str(path), size=size)
    except (OSError, ValueError):
        return None


def _assets_directory() -> Path:
    primary = assets_directory()
    candidates = [primary]
    for candidate in (
        Path(__file__).resolve().parents[1] / "assets",
        Path.cwd() / "assets",
    ):
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        try:
            if (candidate / "fonts").is_dir():
                return candidate
        except OSError:
            continue
    return primary


def _fallback_width(value: str, *, bold: bool, size: int) -> int:
    scale = size / TABLE_FONT_SIZE
    ascii_width = 8.6 if bold else 8.2
    width = 0.0
    for char in value:
        if char.isascii():
            width += ascii_width
        elif _is_wide(char):
            width += 14.5
        else:
            width += 9.5
    return math.ceil(width * scale)


def _is_wide(char: str) -> bool:
    code = ord(char)
    return (
        0x1100 <= code <= 0x115F
        or 0x2E80 <= code <= 0xA4CF
        or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF
        or 0xFE30 <= code <= 0xFE4F
        or 0xFF00 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6
        or 0x1F300 <= code <= 0x1FAFF
        or 0x20000 <= code <= 0x3FFFD
    )
