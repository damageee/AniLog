"""预览图片尺寸计算。"""

from __future__ import annotations

from io import BytesIO

import flet as ft
from PIL import Image


def preview_image_size(
    data: bytes,
    page: ft.Page,
    *,
    max_width: float = 520,
    reserve: float = 220,
) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as im:
        iw, ih = im.size
    max_h = max(200.0, float(page.height or 800) - reserve)
    ratio = min(max_width / iw, max_h / ih, 1.0)
    return max(1, int(iw * ratio)), max(1, int(ih * ratio))
