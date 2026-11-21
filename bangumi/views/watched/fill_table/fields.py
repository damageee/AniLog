"""记录字段与导入条件。"""

from __future__ import annotations

from bangumi.services.bgm_pic import record_has_cover
from bangumi.views.watched.fill_table.constants import FILL_FIELDS
from bangumi.data.watched_data import Record, staff_display


def text(value: object) -> str:
    return str(value or "").strip()


def field_text(record: Record, field: str) -> str:
    """STAFF 按显示文本判断，其余按原始单元格。"""
    if field == "staff":
        return staff_display(record)
    return text(record.get(field))


def info_value(info, field: str, key: str) -> object:
    """STAFF 直接返回字典，其余返回对应字段值。"""
    if field == "staff":
        return info.get("STAFF") or {}
    return info.get(key)


def staff_text(value: dict) -> str:
    """按导演 -> 原作 -> 首个非空值的顺序取显示文本。"""
    for key in ("导演", "原作"):
        text = str(value.get(key) or "").strip()
        if text:
            return text
    for item in value.values():
        text = str(item or "").strip()
        if text:
            return text
    return ""


def info_text(field: str, value: object) -> str:
    if isinstance(value, dict):
        return staff_text(value)
    if field == "tag" and isinstance(value, (list, tuple)):
        return "\n".join(
            str(part).strip() for part in value if str(part).strip()
        )
    return str(value or "").strip()


def fields_complete(record: Record) -> bool:
    return all(
        field_text(record, field) for field, _ in FILL_FIELDS
    )


def needed_keys(
    record: Record,
    fixed: set[str] | frozenset[str] = frozenset(),
    force: bool = False,
) -> list[str]:
    """返回该记录仍需要的信息键（排除固定列）。"""
    return [
        key
        for field, key in FILL_FIELDS
        if field not in fixed
        and (force or not field_text(record, field))
    ]


def has_cover(record: Record) -> bool:
    return record_has_cover(record)


def needs_fill(
    record: Record,
    with_covers: bool,
    force: bool,
    covers_only: bool = False,
    ignore_skip: bool = False,
) -> bool:
    if not ignore_skip and record.get("skip_fill") is True:
        return False
    if covers_only:
        if not force and has_cover(record):
            return False
        return True
    if force:
        return True
    if not fields_complete(record):
        return True
    if not with_covers:
        return False
    return not has_cover(record)


