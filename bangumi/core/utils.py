"""核心通用计算。"""

from __future__ import annotations


def percent(done: int, total: int) -> float:
    """返回 ``done / total`` 的 0..100 值；total 为零时返回 0。"""
    return done / total * 100 if total else 0.0


def text(value: object) -> str:
    return str(value or "").strip()


def to_bgm_id(value: object) -> int:
    """返回存储的 Bangumi id，缺省为 -1。"""
    try:
        return int(value) if value not in (None, "") else -1
    except (TypeError, ValueError):
        return -1


def format_number(value: float, digits: int = 2) -> str:
    text_value = f"{value:.{digits}f}"
    return text_value.rstrip("0").rstrip(".")


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def month_value(year: int, month: int) -> int:
    return year * 12 + month


def month_from_value(value: int) -> tuple[int, int]:
    year = (value - 1) // 12
    return year, value - year * 12
