"""写入记录字段。"""

from __future__ import annotations

from bangumi.views.watched.fill_table.constants import FILL_FIELDS
from bangumi.views.watched.fill_table.fields import info_text, text


def info_values(info) -> dict:
    return {
        field: info_text(field, info.get(key))
        for field, key in FILL_FIELDS
    }


def apply_fields(record, info, *, force: bool, fixed: set[str],
                 rename: bool, searched: bool) -> tuple[list[str], str]:
    returned = info_values(info)
    name_cn = str(info.get("name_cn") or "").strip()
    filled: list[str] = []
    if rename and force and not searched and "anime" not in fixed and name_cn:
        record["former_name"] = str(record.get("anime") or "")
        record["anime"] = name_cn
    if force:
        for field, key in FILL_FIELDS:
            if key in fixed:
                continue
            record[field] = returned[field]
            if returned[field]:
                filled.append(key)
    else:
        for field, key in FILL_FIELDS:
            if key in fixed:
                continue
            if text(record.get(field)):
                continue
            value = returned[field]
            if value:
                record[field] = value
                filled.append(key)
    return filled, name_cn
