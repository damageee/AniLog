"""统计数据类型。"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from bangumi.data.watched_data import Record


DetailItem = tuple[str, Record]

@dataclass(frozen=True)
class OverviewData:
    total: int
    entries: int
    anime_count: int
    tv_count: int
    tv_episodes: int
    ova_count: int
    ova_episodes: int
    oad_count: int
    oad_episodes: int
    sp_count: int
    sp_episodes: int
    movie_count: int
    movie_minutes: int
    feature_count: int
    theater_count: int
    sequel_count: int
    category_counts: list[tuple[str, int]]
    records: list[Record]
    total_items: list[DetailItem]
    entry_items: list[DetailItem]
    anime_items: list[DetailItem]
    tv_items: list[DetailItem]
    ova_items: list[DetailItem]
    oad_items: list[DetailItem]
    sp_items: list[DetailItem]
    movie_items: list[DetailItem]
    sequel_items: list[DetailItem]

@dataclass(frozen=True)
class BroadcastData:
    records: list[Record]
    by_year: dict[int, list[Record]]
    matrix: dict[tuple[int, str], list[Record]]
    season_totals: dict[str, list[Record]]
    years: tuple[int, ...]
    range_years: tuple[int, ...]
    global_max: int

@dataclass(frozen=True)
class CompletionPoint:
    date: dt.date
    record: Record
    episodes: int


@dataclass(frozen=True)
class JourneyData:
    records: list[Record]
    points: list[CompletionPoint]
    months: list[tuple[int, int]]
    month_entries: dict[tuple[int, int], int]
    month_episodes: dict[tuple[int, int], int]
    by_day: dict[dt.date, list[CompletionPoint]]
    by_year: dict[int, dict[dt.date, list[CompletionPoint]]]
