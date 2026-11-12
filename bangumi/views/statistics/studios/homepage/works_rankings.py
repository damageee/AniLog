"""制作公司「全部评分」子页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.watched_data import (
    Record,
    load_records,
    split_studios,
)
from bangumi.views.general.bar_chart import build_bar_chart_view
from bangumi.views.navigation import ENTRY, open_detail, push_view


def _studio_ratings_view(
    page: ft.Page,
    records: list[Record],
    name: str,
    company_records: list[Record],
) -> ft.View:
    from .page import _studio_bar_entries

    route = "/statistics/studios/ratings/" + quote(name, safe="")
    entries, works_by_label = _studio_bar_entries(
        page,
        records,
        company_records,
        lambda rating: True,
    )

    def on_bar_click(label: str) -> None:
        record = works_by_label.get(label)
        if record is None:
            return
        open_detail(page, records, record, ENTRY)

    def rebuild() -> ft.View:
        fresh = load_records()
        fresh_company = [
            record
            for record in fresh
            if name in split_studios(record.get("studio"))
        ]
        return _studio_ratings_view(
            page,
            fresh,
            name,
            fresh_company,
        )

    return build_bar_chart_view(
        page,
        entries,
        max_value=100,
        reverse=False,
        title=f"{name}（评分）",
        route=route,
        decimals=0,
        on_bar_click=on_bar_click,
        rebuild=rebuild,
    )


def _open_studio_ratings(
    page: ft.Page,
    records: list[Record],
    company: str,
    company_records: list[Record],
) -> None:
    name = str(company or "").strip()
    if not name:
        return
    route = "/statistics/studios/ratings/" + quote(name, safe="")
    if (
        page.views
        and getattr(page.views[-1], "route", "") == route
    ):
        return
    push_view(
        page,
        _studio_ratings_view(
            page,
            records,
            name,
            company_records,
        ),
    )
