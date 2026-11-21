"""季度相关页面共用的放送日期与季度辅助函数。"""

from __future__ import annotations


from bangumi.data.dates import (
    BROADCAST_DATE_RE,
    broadcast_dates,
    earliest_broadcast_date,
    start_date,
)
from bangumi.data.sorting import (
    sort_records_by_broadcast,
)

_QUARTER_NAMES = {0: "冬", 1: "春", 2: "夏", 3: "秋"}
_QUARTERS: dict[int, tuple[int, str]] = {
    3: (1, "春"),
    4: (1, "春"),
    5: (1, "春"),
    6: (2, "夏"),
    7: (2, "夏"),
    8: (2, "夏"),
    9: (3, "秋"),
    10: (3, "秋"),
    11: (3, "秋"),
    12: (0, "冬"),
    1: (0, "冬"),
    2: (0, "冬"),
}


def quarter_for_month(month: int) -> tuple[int, str]:
    return _QUARTERS.get(month, (0, "冬"))


def quarter_of_broadcast(text: str) -> tuple[int, int] | None:
    date = start_date(text)
    if date is None:
        return None
    year, month, _ = date
    quarter_index, _ = quarter_for_month(month)
    return year, quarter_index


def quarter_label(year: int, index: int) -> str:
    return f"{year}年{_QUARTER_NAMES[index]}季度"


def quarter_target_key(text: str) -> str:
    target = quarter_of_broadcast(text)
    if target is None:
        return "quarter_works:"
    year, index = target
    return f"quarter_works:{year}:{index}"
