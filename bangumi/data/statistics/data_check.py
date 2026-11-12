"""数据质量检查。"""

from __future__ import annotations

import re

from bangumi.data.dates import earliest_broadcast_date
from bangumi.data.ratings import is_valid_rating
from bangumi.data.sorting import sort_detail_items
from bangumi.data.watched_data import Record, entry_group_key
from .constants import DATA_TAG_SEPARATORS
from .journey import _completion_date
from .models import DetailItem
from .records import _name


def _sort_detail_items(items: list[DetailItem]) -> list[DetailItem]:
    """按最早放送日期排序；无日期的行保持原顺序排在最后。"""
    return sort_detail_items(items)


DATA_FIELDS: tuple[tuple[str, str], ...] = (
    ("category", "类型"),
    ("specification", "规格"),
    ("tag", "TAG"),
    ("author", "作者"),
    ("studio", "制作公司"),
    ("broadcast", "放送"),
    ("role", "角色"),
    ("rating", "评分"),
    ("completion", "补完"),
)


def _data_name(record: Record) -> str:
    return _name(record) or entry_group_key(record) or "未命名"


def data_coverage(records: list[Record]) -> tuple[int, int]:
    """返回 ``(filled_cells, records * valid_columns)``。"""
    filled = 0
    for record in records:
        for field, _ in DATA_FIELDS:
            if str(record.get(field) or "").strip():
                filled += 1
    return filled, len(records) * len(DATA_FIELDS)


def _valid_rating(value: str) -> bool:
    return is_valid_rating(value)


def _duplicate_tags(value: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for part in DATA_TAG_SEPARATORS.split(str(value or "")):
        tag = part.strip()
        key = re.sub(r"\s+", "", tag).casefold()
        if not key:
            continue
        if key in seen:
            if tag not in duplicates:
                duplicates.append(tag)
        else:
            seen.add(key)
    return duplicates


def data_anomalies(
    records: list[Record],
) -> list[tuple[str, list[str]]]:
    """按类型归类数据质量问题，不修改记录。"""
    groups: dict[str, list[str]] = {
        "评分异常": [],
        "放送格式错误": [],
        "补完格式错误": [],
        "重复标签": [],
    }
    for record in records:
        name = _data_name(record)
        rating = str(record.get("rating") or "").strip()
        if rating and not _valid_rating(rating):
            groups["评分异常"].append(f"《{name}》评分：{rating}")
        broadcast = str(record.get("broadcast") or "").strip()
        if broadcast and earliest_broadcast_date(broadcast) is None:
            groups["放送格式错误"].append(
                f"《{name}》放送：{broadcast}"
            )
        completion = str(record.get("completion") or "").strip()
        if completion and _completion_date(completion) is None:
            groups["补完格式错误"].append(
                f"《{name}》补完：{completion}"
            )
        duplicates = _duplicate_tags(str(record.get("tag") or ""))
        if duplicates:
            groups["重复标签"].append(
                f"《{name}》重复标签：{'、'.join(duplicates)}"
            )
    return [
        (title, lines)
        for title, lines in groups.items()
        if lines
    ]


def data_missing_items(records: list[Record]) -> list[DetailItem]:
    """返回缺少任一有效列的行，排序方式与其他列表一致。"""
    items: list[DetailItem] = []
    for record in records:
        missing = [
            label
            for field, label in DATA_FIELDS
            if not str(record.get(field) or "").strip()
        ]
        if not missing:
            continue
        items.append(
            (
                f"《{_data_name(record)}》 —— 缺失"
                f"{'、'.join(missing)}",
                record,
            )
        )
    return _sort_detail_items(items)
