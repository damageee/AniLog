"""评分解析与规范化。"""

from __future__ import annotations


def parse_rating(value) -> int | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    number = int(text)
    if not 0 <= number <= 100:
        return None
    return number


def is_valid_rating(value) -> bool:
    return parse_rating(value) is not None


def normalize_rating(value) -> str:
    number = parse_rating(value)
    return "" if number is None else str(number)
