"""记录字段与导入条件。"""

from __future__ import annotations

from bangumi.services.bgm_pic import record_has_cover
from bangumi.views.watched.fill_table.constants import FILL_FIELDS
from bangumi.data.watched_data import Record


def text(value: object) -> str:
    return str(value or "").strip()


def info_text(field: str, value: object) -> str:
    if field == "tag" and isinstance(value, (list, tuple)):
        return "\n".join(
            str(part).strip() for part in value if str(part).strip()
        )
    return str(value or "").strip()


def fields_complete(record: Record) -> bool:
    return all(text(record.get(field)) for field, _ in FILL_FIELDS)


def needed_keys(
    record: Record,
    fixed: set[str] | frozenset[str] = frozenset(),
    force: bool = False,
) -> list[str]:
    """返回该记录仍需要的信息键（排除固定列）。"""
    return [
        key
        for field, key in FILL_FIELDS
        if key not in fixed
        and (force or not text(record.get(field)))
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


