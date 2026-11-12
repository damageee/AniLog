"""TAG 统计。"""

from __future__ import annotations

from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import Record, split_tags
from .models import DetailItem
from .records import _name


def tag_statistics(records: list[Record]) -> list[tuple[str, int]]:
    """按数量和名称排序返回 ``(tag, record_count)``。"""
    counts: dict[str, int] = {}
    for record in records:
        for tag in split_tags(record.get("tag")):
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )


def filtered_anime_items(
    records: list[Record],
    selected: list[str],
) -> list[DetailItem]:
    """返回包含所有已选标签（AND）的不重复动画名。"""
    wanted = {
        str(tag).strip()
        for tag in selected
        if str(tag or "").strip()
    }
    if not wanted:
        return []

    order: list[str] = []
    names: dict[str, Record] = {}
    earliest: dict[str, tuple[int, int, int]] = {}
    for record in records:
        if not wanted.issubset(split_tags(record.get("tag"))):
            continue
        name = _name(record)
        if not name:
            continue
        if name not in names:
            names[name] = record
            order.append(name)
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        if date is None:
            continue
        current = earliest.get(name)
        if current is None or date < current:
            earliest[name] = date

    dated = [
        (earliest[name], index, name)
        for index, name in enumerate(order)
        if name in earliest
    ]
    dated.sort(key=lambda entry: (entry[0], entry[1]))
    undated = [
        (index, name)
        for index, name in enumerate(order)
        if name not in earliest
    ]
    return [
        (name, names[name]) for _, _, name in dated
    ] + [
        (name, names[name]) for _, name in undated
    ]
