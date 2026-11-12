"""季度作品列表入口。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.data.watched_data import Record, record_title
from bangumi.data.quarter_core import (
    earliest_broadcast_date,
    quarter_for_month,
)
from bangumi.views.navigation import QUARTER_WORKS, open_detail
from bangumi.views.templates.list_page import build_list_view


def _quarter_entries(records: list[Record]) -> list:
    return [
        (record_title(record), record)
        for record in records
    ]


def build_quarter_records_view(
    page: ft.Page,
    *,
    title: str,
    route: str,
    records: list[Record],
    all_records: list[Record],
    before: Callable[[], None] | None = None,
    rebuild: Callable[[], ft.View] | None = None,
) -> ft.View:
    return build_list_view(
        page,
        title=title,
        route=route,
        entries=_quarter_entries(records),
        records=all_records,
        before=before,
        rebuild=rebuild,
    )


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
    return build_quarter_records_view(
        page,
        title=title or "",
        route=route,
        records=selected,
        all_records=records,
        before=before,
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

