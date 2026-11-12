"""放送统计。"""

from __future__ import annotations

from bangumi.data.quarter_core import quarter_for_month
from bangumi.data.watched_data import (
    Record,
    is_tv_specification,
    load_records,
)
from .constants import SEASONS, _BROADCAST_RE
from .models import BroadcastData


def _season_of(month: int) -> str:
    # 保持统计矩阵与权威的
    # 季度映射一致：12/1/2 冬，3/4/5 春，6/7/8 夏，9/10/11 秋。
    return quarter_for_month(month)[1]


def broadcast_data(
    records: list[Record] | None = None,
    *,
    ranges_only: bool = False,
) -> BroadcastData:
    if records is None:
        records = load_records()

    parsed: list[tuple[Record, int, int, bool]] = []
    for record in records:
        broadcast = str(record.get("broadcast") or "")
        has_range = "~" in broadcast or "～" in broadcast
        if ranges_only and not has_range:
            continue
        if ranges_only and not is_tv_specification(
            str(record.get("specification") or "")
        ):
            continue
        match = _BROADCAST_RE.search(broadcast)
        if match is None:
            continue
        year = int(match.group(1))
        month = int(match.group(2))
        if not 1 <= month <= 12:
            continue
        parsed.append((record, year, month, has_range))

    parsed_years = {year for _, year, _, _ in parsed}
    years = (
        tuple(range(min(parsed_years), max(parsed_years) + 1))
        if parsed_years
        else ()
    )
    parsed_range_years = {
        year for _, year, _, has_range in parsed if has_range
    }
    range_years = (
        tuple(range(min(parsed_range_years), max(parsed_range_years) + 1))
        if parsed_range_years
        else ()
    )

    by_year: dict[int, list[Record]] = {year: [] for year in years}
    matrix: dict[tuple[int, str], list[Record]] = {
        (year, season): []
        for year in years
        for season in SEASONS
    }
    season_totals: dict[str, list[Record]] = {
        season: [] for season in SEASONS
    }

    for record, year, month, _ in parsed:
        season = _season_of(month)
        by_year[year].append(record)
        matrix[(year, season)].append(record)
        season_totals[season].append(record)

    global_max = max(
        (len(items) for items in matrix.values()),
        default=0,
    )
    return BroadcastData(
        records=records,
        by_year=by_year,
        matrix=matrix,
        season_totals=season_totals,
        years=years,
        range_years=range_years,
        global_max=global_max,
    )
