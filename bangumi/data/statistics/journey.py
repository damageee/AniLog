"""补完曲线统计。"""

from __future__ import annotations

import datetime as dt

from bangumi.data.watched_data import Record, load_records
from .constants import (
    _BARE_NUMBER_RE,
    _COMPLETION_RE,
    _MAIN_EPISODE_RE,
    _TAG_EPISODE_RE,
)
from .models import CompletionPoint, JourneyData


def _completion_date(value: str) -> dt.date | None:
    match = _COMPLETION_RE.match(str(value or ""))
    if match is None:
        return None
    try:
        return dt.date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    except ValueError:
        return None


def _episode_total(specification: str) -> int:
    text = str(specification or "").upper()
    if not text or "分钟" in text:
        return 0
    main = sum(
        int(match.group(1))
        for match in _MAIN_EPISODE_RE.finditer(text)
    )
    tags = 0
    for match in _TAG_EPISODE_RE.finditer(text):
        tags += int(match.group(1) or 1)
    if main or tags:
        return main + tags
    bare = _BARE_NUMBER_RE.match(text)
    return int(bare.group(1)) if bare else 0


def journey_data(
    records: list[Record] | None = None,
) -> JourneyData:
    if records is None:
        records = load_records()

    points: list[CompletionPoint] = []
    for record in records:
        date = _completion_date(
            str(record.get("completion") or "")
        )
        if date is None:
            continue
        points.append(
            CompletionPoint(
                date=date,
                record=record,
                episodes=_episode_total(
                    str(record.get("specification") or "")
                ),
            )
        )
    points.sort(key=lambda point: point.date)

    if not points:
        return JourneyData(
            records=records,
            points=[],
            months=[],
            month_entries={},
            month_episodes={},
            by_day={},
            by_year={},
        )

    start = (points[0].date.year, points[0].date.month)
    end = (points[-1].date.year, points[-1].date.month)
    months: list[tuple[int, int]] = []
    year, month = start
    while (year, month) <= end:
        months.append((year, month))
        month += 1
        if month > 12:
            year += 1
            month = 1

    month_entries = {key: 0 for key in months}
    month_episodes = {key: 0 for key in months}
    by_day: dict[dt.date, list[CompletionPoint]] = {}
    for point in points:
        key = (point.date.year, point.date.month)
        month_entries[key] += 1
        month_episodes[key] += point.episodes
        by_day.setdefault(point.date, []).append(point)

    by_year: dict[int, dict[dt.date, list[CompletionPoint]]] = {}
    for date, items in by_day.items():
        by_year.setdefault(date.year, {})[date] = items

    return JourneyData(
        records=records,
        points=points,
        months=months,
        month_entries=month_entries,
        month_episodes=month_episodes,
        by_day=by_day,
        by_year=by_year,
    )
