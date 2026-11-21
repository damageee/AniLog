"""按 STAFF 职务搜索人物。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import Record, normalize_staff
from bangumi.ui.colors import foreground_color
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.general.detail_person import open_person_page
from bangumi.views.general.virtual_search import virtual_search_page
from bangumi.views.navigation import push_view
from bangumi.views.statistics.common.shared import _accent
from bangumi.views.widgets.links import highlight_spans


def _staff_candidates(
    records: list[Record],
    key: str,
) -> list[tuple[str, int]]:
    """统计某职务下的人物、出现次数与首次放送日期。"""
    counts: dict[str, int] = {}
    dates: dict[str, tuple[int, int, int] | None] = {}
    for record in records:
        staff = normalize_staff(record.get("staff"))
        value = staff.get(key)
        if not value:
            continue
        names = {
            part.strip()
            for part in str(value).split("、")
            if part.strip()
        }
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        for name in names:
            counts[name] = counts.get(name, 0) + 1
            if name not in dates:
                dates[name] = date
                continue
            current = dates[name]
            if date is not None and (
                current is None or date < current
            ):
                dates[name] = date

    def sort_key(item: tuple[str, int]) -> tuple:
        name, count = item
        date = dates.get(name) or (9999, 12, 31)
        return (-count, date, name)

    return sorted(counts.items(), key=sort_key)


def _staff_key_view(
    page: ft.Page,
    records: list[Record],
    key: str,
    initial_query: str = "",
    rows: list[tuple[str, int]] | None = None,
) -> ft.View:
    """职务搜索页；rows 只统计一次，重建时复用。"""
    name = str(key or "").strip()
    if rows is None:
        rows = _staff_candidates(records, name)
    fg = foreground_color(page)
    highlight = _accent(page, "#FDE68A", "#B45309")

    def row_builder(item, query_text: str) -> ft.Control:
        person, count = item

        def open_person(event: ft.ControlEvent) -> None:
            open_person_page(page, records, person)

        return ft.Container(
            height=40,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.only(
                left=6,
                right=20,
                top=0,
                bottom=0,
            ),
            border_radius=6,
            border=ft.Border(
                bottom=ft.BorderSide(
                    1,
                    ft.Colors.with_opacity(0.1, fg),
                )
            ),
            on_click=open_person,
            tooltip="打开人物页面",
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(
                        spans=highlight_spans(
                            person,
                            query_text,
                            base_style=ui_text_style(
                                size=15,
                                color=fg,
                            ),
                            match_style=ui_text_style(
                                size=15,
                                color=fg,
                                bgcolor=highlight,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                        no_wrap=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ui_text(str(count), size=13, color=fg),
                ],
            ),
        )

    return virtual_search_page(
        page,
        title=name,
        route=f"/watched/staff/{quote(name, safe='')}/search",
        hint_text=f"搜索{name}",
        all_rows=rows,
        row_builder=row_builder,
        initial_query=initial_query,
        rebuild=lambda query: _staff_key_view(
            page,
            records,
            name,
            query,
            rows,
        ),
    )


def open_staff_key_search(
    page: ft.Page,
    records: list[Record],
    key: str,
) -> None:
    """打开某职务的人物搜索页。"""
    name = str(key or "").strip()
    if not name:
        return
    route = f"/watched/staff/{quote(name, safe='')}/search"
    if (
        page.views
        and str(getattr(page.views[-1], "route", "")) == route
    ):
        return
    rows = _staff_candidates(records, name)
    push_view(
        page,
        _staff_key_view(page, records, name, "", rows),
    )
