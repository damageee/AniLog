"""收藏数据：我的喜欢、收藏夹与条目增删改查。"""

from __future__ import annotations

import uuid
from typing import Any

import flet as ft

from bangumi.core.storage import favorites_file, read_json, write_json
from bangumi.data.watched_data import Record

LIKES_ID = "likes"
LIKES_NAME = "我的喜欢"
LIKES_COLOR = "#EC4899"
NEW_FOLDER_COLOR = "#22C55E"
DEFAULT_COLOR = "default"

# 收藏夹色板：第一项跟随主题，其余为高对比配色。
FOLDER_COLORS: tuple[str, ...] = (
    DEFAULT_COLOR,
    "#EF4444",
    "#F97316",
    "#F59E0B",
    "#EAB308",
    "#84CC16",
    "#22C55E",
    "#10B981",
    "#14B8A6",
    "#06B6D4",
    "#0EA5E9",
    "#3B82F6",
    "#6366F1",
    "#8B5CF6",
    "#A855F7",
    "#EC4899",
)


def folder_colors(page: ft.Page, value: str) -> tuple[str, str]:
    """返回收藏夹按钮的 (背景色, 文字色)。"""
    from bangumi.ui.colors import (
        background_color,
        foreground_color,
    )

    text = str(value or "")
    if not text or text == DEFAULT_COLOR:
        return background_color(page), foreground_color(page)
    hex_value = text.lstrip("#")
    if len(hex_value) == 6:
        try:
            r, g, b = (
                int(hex_value[index : index + 2], 16) / 255
                for index in (0, 2, 4)
            )
        except ValueError:
            return text, "#FFFFFF"
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        if luminance > 0.6:
            return text, foreground_color(page)
    return text, "#FFFFFF"


def _normalize_item(value: object) -> dict[str, str] | None:
    """把条目规范化为 {uid, name}；畸形数据返回 None。"""
    if not isinstance(value, dict):
        return None
    return {
        "uid": str(value.get("uid") or "").strip(),
        "name": str(value.get("name") or "").strip(),
    }


def _normalize_folder(value: object) -> dict[str, Any] | None:
    """把收藏夹规范化为 {id, name, color, items}。"""
    if not isinstance(value, dict):
        return None
    folder_id = str(value.get("id") or "").strip()
    if not folder_id:
        folder_id = uuid.uuid4().hex
    raw_items = value.get("items")
    items: list[dict[str, str]] = []
    if isinstance(raw_items, list):
        for entry in raw_items:
            item = _normalize_item(entry)
            if item is not None:
                items.append(item)
    return {
        "id": folder_id,
        "name": str(value.get("name") or "").strip(),
        "color": str(value.get("color") or DEFAULT_COLOR),
        "items": items,
    }


def load_favorites() -> dict:
    """读取收藏数据；缺失或损坏时返回默认结构。"""
    default: dict = {"likes": [], "folders": []}
    path = favorites_file()
    if not path.is_file():
        return default
    try:
        raw = read_json(path)
    except Exception:
        return default
    if not isinstance(raw, dict):
        return default
    likes: list[dict[str, str]] = []
    raw_likes = raw.get("likes")
    if isinstance(raw_likes, list):
        for entry in raw_likes:
            item = _normalize_item(entry)
            if item is not None:
                likes.append(item)
    folders: list[dict[str, Any]] = []
    raw_folders = raw.get("folders")
    if isinstance(raw_folders, list):
        for entry in raw_folders:
            folder = _normalize_folder(entry)
            if folder is not None:
                folders.append(folder)
    return {"likes": likes, "folders": folders}


def save_favorites(data: dict) -> None:
    """原子写回收藏数据。"""
    write_json(favorites_file(), data)


def _find_folder(data: dict, folder_id: str) -> dict | None:
    folders = data.get("folders")
    if not isinstance(folders, list):
        data["folders"] = []
        return None
    for folder in folders:
        if (
            isinstance(folder, dict)
            and str(folder.get("id") or "") == folder_id
        ):
            return folder
    return None


def _items_of(data: dict, folder_id: str) -> list | None:
    """返回收藏夹条目列表；likes 对应 data["likes"]。"""
    if folder_id == LIKES_ID:
        likes = data.get("likes")
        if not isinstance(likes, list):
            data["likes"] = []
        return data["likes"]
    folder = _find_folder(data, folder_id)
    if folder is None:
        return None
    items = folder.get("items")
    if not isinstance(items, list):
        folder["items"] = []
    return folder["items"]


def folder_by_id(data: dict, folder_id: str) -> dict | None:
    """按 id 取收藏夹；likes 返回带 items 的只读视图。"""
    if folder_id == LIKES_ID:
        likes = data.get("likes")
        if not isinstance(likes, list):
            likes = []
        return {
            "id": LIKES_ID,
            "name": LIKES_NAME,
            "color": LIKES_COLOR,
            "items": likes,
        }
    return _find_folder(data, folder_id)


def record_by_uid(
    records: list[Record],
    uid: str,
) -> Record | None:
    """按 uid 找到对应记录。"""
    target = str(uid or "").strip()
    if not target:
        return None
    for record in records:
        if str(record.get("uid") or "").strip() == target:
            return record
    return None


def add_item(
    data: dict,
    folder_id: str,
    uid: str,
    name: str,
    index: int | None = None,
) -> bool:
    """在指定位置插入条目。"""
    items = _items_of(data, folder_id)
    if items is None:
        return False
    item = {"uid": str(uid or "").strip(), "name": str(name or "").strip()}
    if index is None:
        items.append(item)
    else:
        position = max(0, min(int(index), len(items)))
        items.insert(position, item)
    return True


def remove_item(data: dict, folder_id: str, index: int) -> bool:
    items = _items_of(data, folder_id)
    if items is None or not 0 <= index < len(items):
        return False
    items.pop(index)
    return True


def remove_item_by_uid(
    data: dict,
    folder_id: str,
    uid: str,
) -> bool:
    """按 uid 从收藏夹移除条目。"""
    items = _items_of(data, folder_id)
    if items is None:
        return False
    target = str(uid or "").strip()
    for index, item in enumerate(items):
        if (
            isinstance(item, dict)
            and str(item.get("uid") or "").strip() == target
        ):
            items.pop(index)
            return True
    return False


def move_item(
    data: dict,
    folder_id: str,
    index: int,
    delta: int,
) -> bool:
    items = _items_of(data, folder_id)
    if items is None:
        return False
    target = index + delta
    if not 0 <= index < len(items) or not 0 <= target < len(items):
        return False
    items[index], items[target] = items[target], items[index]
    return True


def add_folder(
    data: dict,
    name: str,
    color: str,
    index: int = 0,
) -> dict:
    """新建收藏夹并插入指定位置，返回新收藏夹。"""
    folders = data.get("folders")
    if not isinstance(folders, list):
        folders = []
        data["folders"] = folders
    folder = {
        "id": uuid.uuid4().hex,
        "name": str(name or "").strip(),
        "color": str(color or DEFAULT_COLOR),
        "items": [],
    }
    position = max(0, min(int(index), len(folders)))
    folders.insert(position, folder)
    return folder


def update_folder(
    data: dict,
    folder_id: str,
    name: str,
    color: str,
) -> bool:
    folder = _find_folder(data, folder_id)
    if folder is None:
        return False
    folder["name"] = str(name or "").strip()
    folder["color"] = str(color or DEFAULT_COLOR)
    return True


def remove_folder(data: dict, folder_id: str) -> bool:
    folders = data.get("folders")
    if folder_id == LIKES_ID or not isinstance(folders, list):
        return False
    for index, folder in enumerate(folders):
        if (
            isinstance(folder, dict)
            and str(folder.get("id") or "") == folder_id
        ):
            folders.pop(index)
            return True
    return False


def move_folder(data: dict, index: int, delta: int) -> bool:
    folders = data.get("folders")
    if not isinstance(folders, list):
        return False
    target = index + delta
    if not 0 <= index < len(folders) or not 0 <= target < len(folders):
        return False
    folders[index], folders[target] = folders[target], folders[index]
    return True
