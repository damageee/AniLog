"""评分统计与评分榜单页。"""

from __future__ import annotations

import flet as ft
from bangumi.views.general.bar_chart import (
    build_bar_chart_view,
)
from bangumi.views.navigation import (
    ENTRY,
    open_detail,
    push_view,
)
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_entry,
    record_title,
)
from bangumi.data.ratings import parse_rating
from bangumi.views.statistics.common.shared import range_label


def _open_rating_range(page: ft.Page, start: int, end: int) -> None:
    view = _rating_range_view(page, start, end)
    if page.views and getattr(page.views[-1], "route", "") == view.route:
        return
    push_view(page, view)


def _rating_range_view(
    page: ft.Page,
    start: int,
    end: int,
) -> ft.View:
    records = load_records()
    route = f"/statistics/ratings/range/{start}-{end}"
    title = f"评分（{range_label(start, end)}）"

    valid: list[tuple[Record, int]] = []
    for record in records:
        rating = parse_rating(record.get("rating"))
        if rating is None:
            continue
        if end >= 100:
            if not start <= rating <= 100:
                continue
        elif not start <= rating < end:
            continue
        valid.append((record, rating))

    anime_counts: dict[str, int] = {}
    for record, _ in valid:
        anime = record_title(record)
        if anime:
            anime_counts[anime] = anime_counts.get(anime, 0) + 1

    entries: list[tuple[str, int]] = []
    works_by_label: dict[str, Record] = {}
    for index, (record, rating) in enumerate(valid):
        anime = record_title(record)
        entry = record_entry(record)
        label = anime
        if anime and anime_counts.get(anime, 0) > 1:
            label = f"{anime} · {entry or index}"
        base = label
        suffix = 2
        while label in works_by_label:
            label = f"{base} #{suffix}"
            suffix += 1
        works_by_label[label] = record
        entries.append((label, rating))

    def on_bar_click(label: str) -> None:
        record = works_by_label.get(label)
        if record is not None:
            open_detail(page, records, record, ENTRY)

    def rebuild() -> ft.View:
        return _rating_range_view(page, start, end)

    return build_bar_chart_view(
        page,
        entries,
        max_value=100,
        reverse=False,
        title=title,
        route=route,
        decimals=0,
        on_bar_click=on_bar_click,
        rebuild=rebuild,
    )
