"""写入记录字段。"""

from __future__ import annotations

from bangumi.views.watched.fill_table.constants import FILL_FIELDS
from bangumi.views.watched.fill_table.fields import (
    info_text,
    info_value,
)
from bangumi.data.watched_data import normalize_staff


def info_values(info) -> dict:
    return {
        field: info_text(field, info_value(info, field, key))
        for field, key in FILL_FIELDS
    }


def apply_info_field(record, field: str, info, key: str) -> None:
    """按服务信息写入字段；STAFF 整体替换为字典。"""
    if field == "staff":
        value = info.get("STAFF")
        if isinstance(value, dict):
            record["staff"] = normalize_staff(value)
        else:
            record["staff"] = normalize_staff(
                record.get("staff")
            )
        return
    record[field] = info_text(
        field,
        info_value(info, field, key),
    )


