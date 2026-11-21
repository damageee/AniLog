"""声优统计。"""

from __future__ import annotations

from bangumi.data.role_core import parse_roles
from bangumi.data.watched_data import Record


def cast_statistics(
    records: list[Record],
) -> list[tuple[str, int, Record]]:
    """按作品数降序返回 ``(cv, unique_work_count, sample_record)``。"""
    works: dict[str, set[int]] = {}
    samples: dict[str, Record] = {}
    for index, record in enumerate(records):
        text = str(record.get("role", "") or "")
        for _, cvs in parse_roles(text):
            for cv in cvs:
                name = str(cv or "").strip()
                if not name:
                    continue
                works.setdefault(name, set()).add(index)
                samples.setdefault(name, record)
    items = [
        (name, len(indexes), samples[name])
        for name, indexes in works.items()
    ]
    items.sort(key=lambda item: (-item[1], item[0]))
    return items
