"""追季季度记录的持久化。"""

from __future__ import annotations

from typing import Any

from bangumi.core.storage import read_json, storage_directory, write_json

SEASON_FILE_NAME = "season.json"
QUARTER_COUNT = 4


def season_file():
    return storage_directory() / SEASON_FILE_NAME


def _normalize_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            data: dict[str, Any] = {}
            name = item.strip()
        elif isinstance(item, dict):
            data = dict(item)
            name = str(data.get("name") or "").strip()
        else:
            continue
        if not name or name in seen:
            continue
        seen.add(name)
        data["name"] = name
        data["checked"] = bool(data.get("checked", False))
        result.append(data)
    return result


def _normalize(items: object) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            year = int(item.get("year"))
            quarter = int(item.get("quarter"))
        except (TypeError, ValueError):
            continue
        if not 0 <= quarter < QUARTER_COUNT:
            continue
        key = (year, quarter)
        if key in seen:
            continue
        seen.add(key)
        entry = dict(item)
        entry["year"] = year
        entry["quarter"] = quarter
        entry["items"] = _normalize_items(entry.get("items"))
        result.append(entry)
    result.sort(key=lambda entry: (entry["year"], entry["quarter"]))
    return result


def load_quarters() -> list[dict[str, Any]]:
    """返回已保存的季度；文件缺失或损坏时返回空列表。"""
    path = season_file()
    if not path.is_file():
        return []
    try:
        data = read_json(path)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return _normalize(data.get("quarters"))


def save_quarters(items: list[dict[str, Any]]) -> None:
    write_json(
        season_file(),
        {"quarters": _normalize(items)},
    )


def add_quarter(year: int, index: int) -> bool:
    """创建季度；已存在时返回 False。"""
    year = int(year)
    index = int(index)
    if not 0 <= index < QUARTER_COUNT:
        return False
    quarters = load_quarters()
    if any(
        quarter["year"] == year and quarter["quarter"] == index
        for quarter in quarters
    ):
        return False
    quarters.append(
        {"year": year, "quarter": index, "items": []}
    )
    save_quarters(quarters)
    return True


def get_quarter(year: int, index: int) -> dict | None:
    """返回一个已保存的季度；不存在时返回 None。"""
    try:
        year = int(year)
        index = int(index)
    except (TypeError, ValueError):
        return None
    for quarter in load_quarters():
        if (
            quarter["year"] == year
            and quarter["quarter"] == index
        ):
            return quarter
    return None


def add_items(year: int, index: int, names: list[str]) -> int:
    """向季度追加新条目名；返回新增数量。"""
    try:
        year = int(year)
        index = int(index)
    except (TypeError, ValueError):
        return 0
    quarters = load_quarters()
    target = next(
        (
            quarter
            for quarter in quarters
            if quarter["year"] == year
            and quarter["quarter"] == index
        ),
        None,
    )
    if target is None:
        return 0
    items = target.get("items")
    if not isinstance(items, list):
        items = []
        target["items"] = items
    seen = {
        str(item.get("name") or "") if isinstance(item, dict) else str(item)
        for item in items
    }
    added = 0
    for name in names:
        text = str(name).strip()
        if not text or text in seen:
            continue
        items.append({"name": text, "checked": False})
        seen.add(text)
        added += 1
    if added:
        save_quarters(quarters)
    return added


def delete_quarter(year: int, index: int) -> bool:
    """删除季度；不存在时返回 False。"""
    try:
        year = int(year)
        index = int(index)
    except (TypeError, ValueError):
        return False
    quarters = load_quarters()
    remaining = [
        quarter
        for quarter in quarters
        if not (
            quarter["year"] == year
            and quarter["quarter"] == index
        )
    ]
    if len(remaining) == len(quarters):
        return False
    save_quarters(remaining)
    return True


def _find_quarter(
    quarters: list[dict],
    year: int,
    index: int,
) -> dict | None:
    for quarter in quarters:
        if (
            quarter["year"] == year
            and quarter["quarter"] == index
        ):
            return quarter
    return None


def _items_of(quarter: dict) -> list:
    items = quarter.get("items")
    if not isinstance(items, list):
        items = []
        quarter["items"] = items
    return items


def move_item(
    year: int,
    index: int,
    item_index: int,
    delta: int,
) -> bool:
    """在季度内上移/下移一个条目。"""
    try:
        year = int(year)
        index = int(index)
        item_index = int(item_index)
        delta = int(delta)
    except (TypeError, ValueError):
        return False
    quarters = load_quarters()
    quarter = _find_quarter(quarters, year, index)
    if quarter is None:
        return False
    items = _items_of(quarter)
    target = item_index + delta
    if (
        item_index < 0
        or item_index >= len(items)
        or target < 0
        or target >= len(items)
    ):
        return False
    items[item_index], items[target] = items[target], items[item_index]
    save_quarters(quarters)
    return True


def insert_items(
    year: int,
    index: int,
    before_index: int,
    names: list[str],
) -> int:
    """在 ``before_index`` 之前插入新名称。"""
    try:
        year = int(year)
        index = int(index)
        before_index = int(before_index)
    except (TypeError, ValueError):
        return 0
    quarters = load_quarters()
    quarter = _find_quarter(quarters, year, index)
    if quarter is None:
        return 0
    items = _items_of(quarter)
    before_index = max(0, min(before_index, len(items)))
    seen = {
        str(item.get("name") or "") if isinstance(item, dict) else str(item)
        for item in items
    }
    new_items: list[dict] = []
    for name in names:
        text = str(name).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        new_items.append({"name": text, "checked": False})
    if not new_items:
        return 0
    items[before_index:before_index] = new_items
    save_quarters(quarters)
    return len(new_items)


def delete_item(
    year: int,
    index: int,
    item_index: int,
) -> bool:
    """从季度中删除一个条目。"""
    try:
        year = int(year)
        index = int(index)
        item_index = int(item_index)
    except (TypeError, ValueError):
        return False
    quarters = load_quarters()
    quarter = _find_quarter(quarters, year, index)
    if quarter is None:
        return False
    items = _items_of(quarter)
    if not 0 <= item_index < len(items):
        return False
    items.pop(item_index)
    save_quarters(quarters)
    return True


def set_item_checked(
    year: int,
    index: int,
    item_index: int,
    checked: bool,
) -> bool:
    """持久化一个条目的勾选状态。"""
    try:
        year = int(year)
        index = int(index)
        item_index = int(item_index)
    except (TypeError, ValueError):
        return False
    quarters = load_quarters()
    quarter = _find_quarter(quarters, year, index)
    if quarter is None:
        return False
    items = _items_of(quarter)
    if not 0 <= item_index < len(items):
        return False
    item = items[item_index]
    if not isinstance(item, dict):
        return False
    item["checked"] = bool(checked)
    save_quarters(quarters)
    return True
