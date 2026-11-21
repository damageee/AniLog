"""已追页面的通用辅助。"""

from __future__ import annotations

import html
import re
from pathlib import Path

import flet as ft

from bangumi.core.storage import read_json, storage_directory, write_json
from bangumi.ui.text_metrics import text_width
from bangumi.views.watchlist.constants import (
    BILIBILI_IMPORT_FILE,
    BUTTON_PADDING,
    LABEL_SIZE,
)


def enable_long_press_move_updates() -> None:
    """让长按移动事件载荷与当前 Flet 构建对齐。

    Flet 1.0.5 客户端将移动偏移编码为 ``ofo``，而
    Python 事件类读取 ``of``，因此每次移动更新都会抛出
    ``TypeError: missing ... 'offset_from_origin'`` 并中断拖拽。
    """
    field = ft.LongPressMoveUpdateEvent.__dataclass_fields__.get(
        "offset_from_origin"
    )
    if field is not None and field.metadata.get("data_field") == "of":
        field.metadata = {"data_field": "ofo"}


enable_long_press_move_updates()


def bilibili_import_file() -> Path:
    return storage_directory() / BILIBILI_IMPORT_FILE


def load_bilibili_uid() -> str:
    """返回上次成功使用的 UID；优先读 preferences，旧文件作兜底。"""
    try:
        from bangumi.data.preferences import Preferences

        uid = Preferences.load().bilibili_uid
        if uid:
            return uid
    except Exception:
        pass
    try:
        path = bilibili_import_file()
        if not path.is_file():
            return ""
        data = read_json(path)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    uid = data.get("uid")
    if uid is None:
        return ""
    text = str(uid).strip()
    return text if text.isdigit() else ""


def save_bilibili_uid(uid: str) -> None:
    """写入 preferences；失败时回退旧文件，绝不中断导入流程。"""
    try:
        from bangumi.data.preferences import Preferences

        prefs = Preferences.load()
        prefs.bilibili_uid = str(uid).strip()
        prefs.save()
        return
    except Exception:
        pass
    try:
        write_json(
            bilibili_import_file(),
            {"uid": str(uid)},
        )
    except Exception:
        pass


def clean_bilibili_title(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def has_animation_style(item: dict) -> bool:
    styles = item.get("styles")
    if isinstance(styles, str):
        styles = [styles]
    if not isinstance(styles, (list, tuple)):
        return False
    return any("动画" in str(style) for style in styles)


def fit_label(name: str, width: int) -> str:
    limit = max(8, width - BUTTON_PADDING * 2 - 4)
    if text_width(name, size=LABEL_SIZE) <= limit:
        return name
    suffix = "..."
    text = name
    while text and (
        text_width(text + suffix, size=LABEL_SIZE) > limit
    ):
        text = text[:-1]
    return f"{text}{suffix}" if text else suffix
