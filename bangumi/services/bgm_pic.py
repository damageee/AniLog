"""获取 Bangumi 条目的封面图片。

用法：
    data = get_subject_image(225604)          # medium，失败时回退到 common
    data = get_subject_image(225604, image_type="large")

返回原始图片字节；两次请求都失败时返回 ``None``。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from bangumi.services.bgm_search import (
    _user_agent,
    current_proxies,
    mark_proxy_dead,
)
from bangumi.core.storage import storage_directory

API_ROOT = "https://api.bgm.tv/v0/subjects"
TIMEOUT = 10
DEFAULT_TYPE = "medium"
FALLBACK_TYPE = "common"
COVER_DIRECTORY = "bgm_cover"


def _get_image(url: str, image_type: str) -> requests.Response | None:
    headers = {
        "User-Agent": _user_agent(),
        "Accept": "image/*",
    }
    params = {"type": image_type}
    try:
        return requests.get(
            url,
            params=params,
            headers=headers,
            timeout=TIMEOUT,
            proxies=current_proxies(),
        )
    except requests.exceptions.ProxyError:
        mark_proxy_dead()
        try:
            return requests.get(
                url,
                params=params,
                headers=headers,
                timeout=TIMEOUT,
                proxies={"http": None, "https": None},
            )
        except Exception:
            return None
    except Exception:
        return None


def get_subject_image(
    subject_id: int | str,
    *,
    image_type: str = DEFAULT_TYPE,
) -> bytes | None:
    """返回单个条目的图片字节；失败时返回 ``None``。"""
    try:
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return None

    url = f"{API_ROOT}/{subject_id}/image"
    candidates: list[str] = []
    for kind in (str(image_type or DEFAULT_TYPE), FALLBACK_TYPE):
        if kind and kind not in candidates:
            candidates.append(kind)

    for kind in candidates:
        response = _get_image(url, kind)
        if response is None or response.status_code != 200:
            continue
        content = response.content
        content_type = response.headers.get("Content-Type", "")
        if not content:
            continue
        if content_type and not content_type.startswith("image/"):
            continue
        return content
    return None


def cover_path(subject_id: int | str) -> Path | None:
    try:
        sid = int(subject_id)
    except (TypeError, ValueError):
        return None
    return storage_directory() / COVER_DIRECTORY / f"{sid}.jpg"


def save_subject_image(subject_id: int | str) -> Path | None:
    path = cover_path(subject_id)
    if path is None:
        return None
    data = get_subject_image(subject_id)
    if not data:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    try:
        with Image.open(BytesIO(data)) as image:
            image.convert("RGB").save(path, format="JPEG", quality=92)
    except Exception:
        try:
            path.write_bytes(data)
        except OSError:
            return None
    return path if path.is_file() else None


def has_cover(bgm_id) -> bool:
    if not isinstance(bgm_id, int) or bgm_id == -1:
        return False
    path = cover_path(bgm_id)
    return path is not None and path.is_file()


def record_has_cover(record) -> bool:
    return has_cover(record.get("bgm_id"))


__all__ = ["get_subject_image", "has_cover", "record_has_cover"]
