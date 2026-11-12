"""声优统计。"""

from __future__ import annotations

from bangumi.data.role_core import parse_roles
from bangumi.data.watched_data import Record, entry_group_key


def cast_statistics(
    records: list[Record],
) -> list[tuple[str, int, Record]]:
    """按数量降序返回 ``(cv, unique_entry_count, sample_record)``。"""
    entries: dict[str, set[str]] = {}
    samples: dict[str, Record] = {}
    for record in records:
        key = entry_group_key(record)
        if not key:
            continue
        text = str(record.get("role", "") or "")
        for _, cvs in parse_roles(text):
            for cv in cvs:
                name = str(cv or "").strip()
                if not name:
                    continue
                entries.setdefault(name, set()).add(key)
                samples.setdefault(name, record)
    items = [
        (name, len(keys), samples[name])
        for name, keys in entries.items()
    ]
    items.sort(key=lambda item: (-item[1], item[0]))
    return items
