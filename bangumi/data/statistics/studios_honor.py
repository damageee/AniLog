"""制作公司荣誉榜指标。"""

from __future__ import annotations

import colorsys
import hashlib
import math

from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.ratings import parse_rating
from bangumi.data.watched_data import Record, split_studios
from .constants import HONOR_TOTAL


def _honor_rating(record: Record) -> int | None:
    return parse_rating(record.get("rating"))


def _honor_year(record: Record) -> int | None:
    date = earliest_broadcast_date(
        str(record.get("broadcast") or "")
    )
    return date[0] if date is not None else None


def _honor_studios(record: Record) -> list[str]:
    return split_studios(record.get("studio"))


def _honor_group(records: list[Record]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for record in records:
        rating = _honor_rating(record)
        for studio in _honor_studios(record):
            group = groups.setdefault(
                studio,
                {
                    "count": 0,
                    "sum": 0,
                    "rated": 0,
                    "max": None,
                },
            )
            group["count"] += 1
            if rating is None:
                continue
            group["sum"] += rating
            group["rated"] += 1
            if group["max"] is None or rating > group["max"]:
                group["max"] = rating
    result: dict[str, dict] = {}
    for studio, group in groups.items():
        rated = int(group["rated"])
        result[studio] = {
            "count": int(group["count"]),
            "avg": group["sum"] / rated if rated else None,
            "max": group["max"],
            "rated": rated,
        }
    return result


def _honor_percentile_threshold(
    counts: list[int],
    ratio: float = 0.65,
) -> int:
    if not counts:
        return 0
    ordered = sorted(counts)
    index = max(
        0,
        math.ceil(ratio * len(ordered)) - 1,
    )
    return ordered[index]


def _honor_sort_key(
    column: str,
    item: tuple[str, dict],
) -> tuple:
    name, stats = item
    if column == "高产劳模":
        return (
            -stats["count"],
            -stats["rated"],
            -(stats["avg"] if stats["avg"] is not None else -1),
            -(stats["max"] if stats["max"] is not None else -1),
            name,
        )
    if column == "整体发挥":
        return (
            -stats["avg"],
            -stats["rated"],
            -(stats["max"] if stats["max"] is not None else -1),
            name,
        )
    return (
        -stats["max"],
        -stats["rated"],
        -(stats["avg"] if stats["avg"] is not None else -1),
        name,
    )


def _honor_rank(
    column: str,
    groups: dict[str, dict],
) -> list[tuple[str, dict]]:
    items = list(groups.items())
    if column == "整体发挥":
        items = [
            item for item in items if item[1]["avg"] is not None
        ]
    elif column == "最高力作":
        items = [
            item for item in items if item[1]["max"] is not None
        ]
    return sorted(items, key=lambda item: _honor_sort_key(column, item))


def _company_color(name: str, dark: bool) -> str:
    digest = hashlib.md5(name.encode("utf-8")).digest()
    hue = ((digest[0] << 8) | digest[1]) % 360 / 360
    if dark:
        r, g, b = colorsys.hsv_to_rgb(hue, 0.38, 0.38)
    else:
        r, g, b = colorsys.hsv_to_rgb(hue, 0.22, 0.94)
    return "#{:02X}{:02X}{:02X}".format(
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)),
    )


def _honor_metrics(
    column: str,
    label: str,
    groups: dict[str, dict],
) -> dict:
    total_avg = column == "整体发挥" and label == HONOR_TOTAL
    eligible = groups
    if total_avg:
        counts = [
            int(item["count"])
            for item in groups.values()
        ]
        threshold = _honor_percentile_threshold(counts)
        eligible = {
            name: item
            for name, item in groups.items()
            if int(item["count"]) >= threshold
        }
    ranked = _honor_rank(
        column,
        eligible if total_avg else groups,
    )
    if not ranked:
        return {"empty": True}

    studio, stats = ranked[0]
    if column == "高产劳模":
        value = stats["count"]
    elif column == "整体发挥":
        value = round(stats["avg"])
    else:
        value = stats["max"]

    if column == "高产劳模":
        arr = [
            (name, item["count"])
            for name, item in ranked
        ]
        decimals = 0
        pool = groups

        def metric(item: dict) -> int:
            return int(item["count"])
    elif column == "整体发挥":
        arr = [
            (name, item["avg"])
            for name, item in ranked
            if item["avg"] is not None
        ]
        decimals = 2
        pool = eligible if total_avg else groups

        def metric(item: dict) -> object:
            return item["avg"]
    else:
        arr = [
            (name, item["max"])
            for name, item in ranked
            if item["max"] is not None
        ]
        decimals = 0
        pool = groups

        def metric(item: dict) -> object:
            return item["max"]

    metric_values = [
        (name, metric(item))
        for name, item in pool.items()
        if metric(item) is not None
    ]
    best_value = max(
        (value for _, value in metric_values),
        default=None,
    )
    primary_tied = (
        [
            name
            for name, value in metric_values
            if value == best_value
        ]
        if best_value is not None
        else []
    )

    remark = (
        "「总览×整体发挥」项仅制作数>=65百分位的公司参与排行"
        if total_avg
        else ""
    )
    return {
        "empty": False,
        "original": studio,
        "value": value,
        "primary_tied": primary_tied,
        "arr": arr,
        "decimals": decimals,
        "remark": remark,
    }
