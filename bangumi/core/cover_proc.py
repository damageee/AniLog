"""封面图缩放、裁切与模糊填充处理。"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter

# 封面宽高比（约 480:679）。
_COVER_RATIO = 480 / 679

_RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS

# 缩略图内存缓存：key 为 (bgm_id, 宽度)。
_THUMB_CACHE: dict[tuple[int, int], bytes] = {}
_THUMB_CACHE_LIMIT = 1200

__all__ = [
    "invalidate_cover",
    "processed_cover",
    "process_cover_bytes",
]


def invalidate_cover(bgm_id: int) -> None:
    """清除某个条目的全部缩略图缓存。"""
    for key in [k for k in _THUMB_CACHE if k[0] == bgm_id]:
        _THUMB_CACHE.pop(key, None)


def process_cover_bytes(raw: bytes, width: int) -> bytes | None:
    """把封面 bytes 按 480:679 裁切并填充模糊背景，返回 JPEG。"""
    try:
        with Image.open(BytesIO(raw)) as image:
            img = image.convert("RGB")
        W, H = img.size
        if not W or not H:
            return None
        # 先在原图尺寸下计算裁切参数，随后整体按比例缩小。
        if W / H < _COVER_RATIO:
            H2 = (H + W / _COVER_RATIO) / 2
            W2 = _COVER_RATIO * H2
            top = min(max(0.4 * H - H2 / 2, 0), H - H2)
            crop_box = (0, top, W, top + H2)
            canvas_size = (W2, H2)
            paste_at = ((W2 - W) / 2, 0)
        elif W / H > _COVER_RATIO:
            W2 = (W + H * _COVER_RATIO) / 2
            H2 = W2 / _COVER_RATIO
            left = min(max(0.5 * W - W2 / 2, 0), W - W2)
            crop_box = (left, 0, left + W2, H)
            canvas_size = (W2, H2)
            paste_at = (0, (H2 - H) / 2)
        else:
            W2, H2 = W, H
            crop_box = (0, 0, W, H)
            canvas_size = (W, H)
            paste_at = (0, 0)

        scale = width / W2
        if scale >= 1:
            sw, sh = W, H
        else:
            # 缩放尺寸用 round，避免向下取整后裁切越界。
            sw = max(1, int(round(W * scale)))
            sh = max(1, int(round(H * scale)))
            img = img.resize((sw, sh), _RESAMPLE)

        # 裁切坐标缩放后取整并夹紧在图像范围内，避免补出黑边。
        x0, y0, x1, y1 = (
            int(round(v * scale)) for v in crop_box
        )
        x0 = max(0, min(x0, sw - 1))
        y0 = max(0, min(y0, sh - 1))
        x1 = max(x0 + 1, min(x1, sw))
        y1 = max(y0 + 1, min(y1, sh))
        fg = img.crop((x0, y0, x1, y1))

        # 画布尺寸：scale >= 1 时保持原尺寸。
        if scale >= 1:
            cw = max(1, int(round(canvas_size[0])))
            ch = max(1, int(round(canvas_size[1])))
        else:
            cw = max(1, int(round(canvas_size[0] * scale)))
            ch = max(1, int(round(canvas_size[1] * scale)))
        bg = img.resize((cw, ch), _RESAMPLE)
        # 在缩略图尺寸上模糊，半径保持在 3~6 左右。
        bg = bg.filter(
            ImageFilter.GaussianBlur(
                radius=max(1.0, min(cw, ch) * 0.05)
            )
        )
        bg = ImageEnhance.Brightness(bg).enhance(0.75)
        # 极端情况下先把超出画布的裁掉，再夹紧粘贴位置。
        if fg.width > cw or fg.height > ch:
            fg = fg.crop(
                (
                    0,
                    0,
                    min(fg.width, cw),
                    min(fg.height, ch),
                )
            )
        px = int(round(paste_at[0] * scale))
        py = int(round(paste_at[1] * scale))
        px = min(max(0, px), max(0, cw - fg.width))
        py = min(max(0, py), max(0, ch - fg.height))
        bg.paste(fg, (px, py))
        out_h = max(
            1,
            int(round(width / _COVER_RATIO)),
        )
        bg = bg.resize(
            (max(1, width), out_h),
            _RESAMPLE,
        )
        buffer = BytesIO()
        bg.save(buffer, format="JPEG", quality=80)
        data = buffer.getvalue()
    except Exception:
        return None

    return data


def processed_cover(bgm_id: int, width: int) -> bytes | None:
    """读取原图后调用 process_cover_bytes，并缓存结果。"""
    from bangumi.services.bgm_pic import cover_path

    key = (bgm_id, width)
    cached = _THUMB_CACHE.get(key)
    if cached is not None:
        return cached
    path = cover_path(bgm_id)
    if path is None or not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    data = process_cover_bytes(raw, width)
    if data is None:
        return None
    if len(_THUMB_CACHE) > _THUMB_CACHE_LIMIT:
        _THUMB_CACHE.clear()
    _THUMB_CACHE[key] = data
    return data
