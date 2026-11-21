"""TAG 统计。"""

from __future__ import annotations

import datetime as dt

from bangumi.data.dates import parse_iso_date
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.ratings import parse_rating
from bangumi.data.watched_data import Record, split_tags
from .models import DetailItem
from .records import _name

TAG_SORT_OPTIONS = (
    ("broadcast_asc", "按放送日期升序"),
    ("broadcast_desc", "按放送日期降序"),
    ("rating_asc", "按评分升序"),
    ("rating_desc", "按评分降序"),
    ("completion_asc", "按补完日期升序"),
    ("completion_desc", "按补完日期降序"),
)
DEFAULT_TAG_SORT = "broadcast_asc"
DEFAULT_TAG_ORDER = (
    "broadcast_asc",
    "rating_desc",
    "completion_asc",
)


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
    sort_mode: str = DEFAULT_TAG_SORT,
) -> list[DetailItem]:
    """返回包含所有已选标签（AND）的不重复动画名。"""
    wanted = {
        str(tag).strip()
        for tag in selected
        if str(tag or "").strip()
    }
    if not wanted:
        return []
    valid_modes = {mode for mode, _ in TAG_SORT_OPTIONS}
    if sort_mode not in valid_modes:
        sort_mode = DEFAULT_TAG_SORT

    order: list[str] = []
    names: dict[str, Record] = {}
    for record in records:
        if not wanted.issubset(split_tags(record.get("tag"))):
            continue
        name = _name(record)
        if not name:
            continue
        if name not in names:
            names[name] = record
            order.append(name)

    def date_ordinal(value: str) -> int | None:
        parsed = parse_iso_date(value)
        if parsed is None:
            return None
        return parsed.toordinal()

    def broadcast_ordinal(record: Record) -> int | None:
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        if date is None:
            return None
        return dt.date(*date).toordinal()

    def mode_key(name: str, mode: str) -> tuple[int, int]:
        record = names[name]
        descending = mode.endswith("_desc")
        if mode.startswith("rating"):
            value = parse_rating(record.get("rating")) or 0
        elif mode.startswith("broadcast"):
            value = broadcast_ordinal(record)
        else:
            value = date_ordinal(
                str(record.get("completion") or "")
            )
        if value is None:
            # 缺失值永远排在最后。
            return (1, 0)
        return (0, -value if descending else value)

    modes = [sort_mode] + [
        mode for mode in DEFAULT_TAG_ORDER if mode != sort_mode
    ]
    result = list(order)
    # 稳定排序：按优先级从低到高依次排序。
    for mode in reversed(modes):
        result.sort(key=lambda name: mode_key(name, mode))
    return [(name, names[name]) for name in result]
