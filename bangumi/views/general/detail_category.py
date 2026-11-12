"""类别作品列表页。"""

from __future__ import annotations

from typing import Callable
from urllib.parse import quote

import flet as ft

from bangumi.data.sorting import sort_detail_items
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_title,
)
from bangumi.views.templates.list_page import (
    build_list_view,
    open_list_page,
)


def _category_records(
    records: list[Record],
    name: str,
) -> list[Record]:
    return [
        record
        for record in records
        if str(record.get("category", "") or "").strip() == name
    ]


def _category_entries(
    records: list[Record],
) -> list[tuple[str, Record]]:
    return sort_detail_items(
        [(record_title(record), record) for record in records]
    )


def _category_title(clicked: Record) -> str:
    return (
        str(clicked.get("category", "") or "").strip()
        or "类型"
    )


def build_category_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
    *,
    before: Callable[[], None] | None = None,
) -> ft.View:
    title = _category_title(clicked)
    matches = _category_records(records, title)
    if not matches:
        matches = [clicked]
    return build_list_view(
        page,
        title=title,
        route=route,
        entries=_category_entries(matches),
        records=records,
        before=before,
        rebuild=lambda: build_category_view(
            page,
            load_records(),
            clicked,
            route,
            before=before,
        ),
    )


def open_category_page(
    page: ft.Page,
    records: list[Record],
    category: str,
    *,
    before: Callable[[], None] | None = None,
) -> None:
    """从任意页面打开某个类别的作品列表。"""
    name = str(category or "").strip()
    if not name:
        return
    route = f"/statistics/categories/{quote(name, safe='')}"

    def rebuild() -> ft.View:
        fresh = load_records()
        return build_list_view(
            page,
            title=name,
            route=route,
            entries=_category_entries(
                _category_records(fresh, name)
            ),
            records=fresh,
            before=before,
        )

    open_list_page(
        page,
        title=name,
        route=route,
        entries=_category_entries(
            _category_records(records, name)
        ),
        records=records,
        before=before,
        rebuild=rebuild,
    )
