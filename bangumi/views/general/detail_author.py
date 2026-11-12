"""作者作品列表页。"""

from __future__ import annotations

from typing import Callable
from urllib.parse import quote

import flet as ft

from bangumi.data.sorting import sort_detail_items
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_title,
    split_authors,
)
from bangumi.views.templates.list_page import (
    build_list_view,
    open_list_page,
)


def _author_records(
    records: list[Record],
    name: str,
) -> list[Record]:
    return [
        record
        for record in records
        if name in split_authors(record.get("author"))
    ]


def _author_entries(
    records: list[Record],
) -> list[tuple[str, Record]]:
    return sort_detail_items(
        [(record_title(record), record) for record in records]
    )


def _author_title(clicked: Record) -> str:
    names = split_authors(str(clicked.get("author", "") or ""))
    if len(names) == 1:
        return names[0]
    return str(clicked.get("author", "") or "").strip() or "作者"


def build_author_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
    *,
    before: Callable[[], None] | None = None,
) -> ft.View:
    names = split_authors(str(clicked.get("author", "") or ""))
    title = _author_title(clicked)
    if len(names) == 1:
        matches = _author_records(records, names[0])
    else:
        matches = [
            record
            for record in records
            if str(record.get("author", "") or "").strip() == title
        ]
    if not matches:
        matches = [clicked]
    return build_list_view(
        page,
        title=title,
        route=route,
        entries=_author_entries(matches),
        records=records,
        before=before,
        rebuild=lambda: build_author_view(
            page,
            load_records(),
            clicked,
            route,
            before=before,
        ),
    )


def open_author_page(
    page: ft.Page,
    records: list[Record],
    author: str,
    *,
    before: Callable[[], None] | None = None,
) -> None:
    """从任意页面打开某位作者的作品列表。"""
    name = str(author or "").strip()
    if not name:
        return
    route = f"/statistics/authors/{quote(name, safe='')}"

    def rebuild() -> ft.View:
        fresh = load_records()
        return build_list_view(
            page,
            title=name,
            route=route,
            entries=_author_entries(
                _author_records(fresh, name)
            ),
            records=fresh,
            before=before,
        )

    open_list_page(
        page,
        title=name,
        route=route,
        entries=_author_entries(_author_records(records, name)),
        records=records,
        before=before,
        rebuild=rebuild,
    )
