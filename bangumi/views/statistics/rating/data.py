"""评分相关纯计算。"""

from __future__ import annotations


def monthly_series(
    pairs: list[tuple[tuple[int, int, int], int]],
) -> tuple[list[tuple[int, int]], list[float]]:
    keys = sorted({(date[0], date[1]) for date, _ in pairs})
    if not keys:
        return [], []
    sums: dict[tuple[int, int], int] = {}
    counts: dict[tuple[int, int], int] = {}
    for date, value in pairs:
        key = (date[0], date[1])
        sums[key] = sums.get(key, 0) + value
        counts[key] = counts.get(key, 0) + 1
    months: list[tuple[int, int]] = []
    year, month = keys[0]
    last = keys[-1]
    while (year, month) <= last:
        months.append((year, month))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    values = [
        sums[key] / counts[key] if counts.get(key) else 0.0
        for key in months
    ]
    return months, values


def quarterly_series(
    groups: dict[tuple[int, int], list[int]],
) -> tuple[list[tuple[int, int]], list[float]]:
    keys = sorted(groups)
    if not keys:
        return [], []
    quarters: list[tuple[int, int]] = []
    year, index = keys[0]
    last = keys[-1]
    while (year, index) <= last:
        quarters.append((year, index))
        index += 1
        if index > 3:
            year, index = year + 1, 0
    values = [
        (
            sum(groups[key]) / len(groups[key])
            if groups.get(key)
            else 0.0
        )
        for key in quarters
    ]
    return quarters, values


def cumulative_series(
    months: list[tuple[int, int]],
    pairs: list[tuple[tuple[int, int, int], int]],
) -> list[float]:
    sums: dict[tuple[int, int], int] = {}
    counts: dict[tuple[int, int], int] = {}
    for date, value in pairs:
        key = (date[0], date[1])
        sums[key] = sums.get(key, 0) + value
        counts[key] = counts.get(key, 0) + 1
    total = 0
    count = 0
    values: list[float] = []
    for key in months:
        if counts.get(key):
            total += sums[key]
            count += counts[key]
            values.append(total / count)
        else:
            values.append(values[-1] if values else 0.0)
    return values
