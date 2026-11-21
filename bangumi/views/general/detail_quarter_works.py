"""季度作品列表入口。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.data.watched_data import Record, record_title
from bangumi.data.ratings import parse_rating
from bangumi.data.quarter_core import (
    earliest_broadcast_date,
    quarter_for_month,
)
from bangumi.views.general.bar_chart import build_bar_chart_view
from bangumi.views.navigation import (
    ENTRY,
    QUARTER_WORKS,
    open_detail,
)


def _quarter_entries(records: list[Record]) -> list:
    return [
        (record_title(record), record)
        for record in records
    ]


def build_quarter_works_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
    *,
    title: str | None = None,
    selected: list[Record] | None = None,
    before: Callable[[], None] | None = None,
    rebuild: Callable[[], ft.View] | None = None,
) -> ft.View | None:
    if selected is None:
        date = earliest_broadcast_date(
            str(clicked.get("broadcast") or "")
        )
        if date is None:
            return None
        index, season = quarter_for_month(date[1])
        rows = []
        for record in records:
            other = earliest_broadcast_date(
                str(record.get("broadcast") or "")
            )
            if other is None:
                continue
            if (
                other[0] == date[0]
                and quarter_for_month(other[1])[0] == index
            ):
                rows.append(record)
        selected = rows
        if title is None:
            title = f"{date[0]}{season}季度"
    # 横条竞赛：arr = 该季度所有作品的动画名与评分（无评分按 0）。
    items = list(selected or [])
    labels = [record_title(record) for record in items]
    record_by_label = dict(zip(labels, items))

    def click(label: str) -> None:
        record = record_by_label.get(label)
        if record is None:
            return
        if before is not None:
            before()
        open_detail(page, records, record, ENTRY)

    return build_bar_chart_view(
        page,
        [
            (label, float(parse_rating(record.get("rating")) or 0))
            for label, record in zip(labels, items)
        ],
        max_value=100.0,
        title=title or "",
        route=route,
        decimals=0,
        on_bar_click=click,
        rebuild=rebuild,
    )


def open_quarter_works_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    value: str | None = None,
) -> None:
    """打开某条记录放送日期对应的季度作品列表。"""
    open_detail(page, records, record, QUARTER_WORKS, value=value)

