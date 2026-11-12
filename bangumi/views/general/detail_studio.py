"""制作公司作品列表页。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.data.sorting import sort_detail_items
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_title,
    split_studios,
)
from bangumi.views.templates.list_page import build_list_view


def build_studio_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
    *,
    title: str | None = None,
    before: Callable[[], None] | None = None,
) -> ft.View:
    name = str(clicked.get("studio") or "").strip()
    matches = [
        record
        for record in records
        if name in split_studios(record.get("studio"))
    ]
    if not matches:
        matches = [clicked]
    resolved = title or name or "制作公司"
    entries = sort_detail_items(
        [(record_title(record), record) for record in matches]
    )
    return build_list_view(
        page,
        title=resolved,
        route=route,
        entries=entries,
        records=records,
        before=before,
        copy_title=True,
        rebuild=lambda: build_studio_view(
            page,
            load_records(),
            clicked,
            route,
            title=title,
            before=before,
        ),
    )
