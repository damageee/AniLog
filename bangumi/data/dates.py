"""日期解析与格式化。"""

from __future__ import annotations

import datetime as dt
import re

BROADCAST_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_TIME_SUFFIX = re.compile(
    r"\s+\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?"
)
_CHINESE_DATE = re.compile(
    r"^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日$"
)
_NUMERIC_DATE = re.compile(
    r"^(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})$"
)


def broadcast_dates(text: str) -> list[tuple[int, int, int]]:
    """返回 ``text`` 中所有完整的放送日期。"""
    return [
        (int(year), int(month), int(day))
        for year, month, day in BROADCAST_DATE_RE.findall(
            str(text or "")
        )
    ]


def earliest_broadcast_date(
    text: str,
) -> tuple[int, int, int] | None:
    """返回最早的放送日期；无日期时返回 ``None``。"""
    dates = broadcast_dates(text)
    return min(dates) if dates else None


def start_date(text: str) -> tuple[int, int, int] | None:
    return earliest_broadcast_date(text)


def parse_iso_date(value: str) -> dt.date | None:
    """解析中文或数字形式的完整日期。"""
    text = _TIME_SUFFIX.sub("", value or "").strip()
    for pattern in (_CHINESE_DATE, _NUMERIC_DATE):
        match = pattern.match(text)
        if match is None:
            continue
        year, month, day = (int(part) for part in match.groups())
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    return None


def format_display_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(
        r"(\d{4})(?:\D+(\d{1,2}))?(?:\D+(\d{1,2}))?",
        text,
    )
    if match is None:
        return text
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return text
    return f"{year:04d}年{month:02d}月{day:02d}日"


def format_iso_date(
    value: dt.date | None,
    *,
    choose: str = "选择日期",
) -> str:
    if value is None:
        return choose
    return f"{value.year}年{value.month}月{value.day}日"


def parse_broadcast_date(
    value: str,
) -> tuple[int, int, int] | None:
    dates = broadcast_dates(value)
    return dates[0] if dates else None
