"""条目 STAFF 详情页：展示职务与姓名。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.watched_data import Record, staff_items
from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import hover_link
from bangumi.ui.layout import vertical_page
from bangumi.ui.theme import ui_text
from bangumi.views.general.detail_person import open_person_page
from bangumi.views.general.staff_search import (
    open_staff_key_search,
)
from bangumi.views.navigation import push_view
from bangumi.views.statistics.common.shared import _back_view


def _anime_name(record: Record) -> str:
    return str(
        record.get("anime") or record.get("entry") or ""
    ).strip()


def _staff_value_controls(
    page: ft.Page,
    records: list[Record],
    value: str,
    fg: str,
) -> list[ft.Control]:
    parts = [
        part.strip()
        for part in str(value or "").split("、")
        if part.strip()
    ]
    controls: list[ft.Control] = []
    for index, part in enumerate(parts):
        if index:
            controls.append(ui_text("、", size=14, color=fg))
        controls.append(
            hover_link(
                page,
                ui_text(part, size=14),
                fg,
                lambda event, n=part: open_person_page(
                    page,
                    records,
                    n,
                ),
            )
        )
    return controls


def build_staff_view(
    page: ft.Page,
    records: list[Record],
    record: Record,
    route: str,
) -> ft.View:
    """展示单条记录的 STAFF 键值对。"""
    anime = _anime_name(record)
    title = f"{anime}（STAFF）" if anime else "STAFF"
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    staff = staff_items(record.get("staff"))
    rows: list[ft.Control] = []
    for key, value in staff:
        rows.append(
            ft.Row(
                wrap=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    hover_link(
                        page,
                        ui_text(
                            key,
                            size=14,
                            weight=ft.FontWeight.BOLD,
                        ),
                        fg,
                        lambda event, k=key: (
                            open_staff_key_search(
                                page,
                                records,
                                k,
                            )
                        ),
                    ),
                    ui_text("：", size=14, color=fg),
                    *_staff_value_controls(
                        page,
                        records,
                        value,
                        fg,
                    ),
                ],
            )
        )
    if not rows:
        rows = [
            ui_text("暂无 STAFF", size=12, color=secondary)
        ]
    column = ft.Column(spacing=6, controls=rows)
    return _back_view(
        page,
        route=route,
        title=title,
        controls=[vertical_page([column], stretch=True)],
        rebuild=lambda: build_staff_view(
            page,
            records,
            record,
            route,
        ),
    )


def open_staff_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
) -> None:
    """打开指定记录的 STAFF 详情页。"""
    anime = _anime_name(record)
    route = f"/watched/staff/{quote(anime, safe='')}"
    if (
        page.views
        and str(getattr(page.views[-1], "route", "")) == route
    ):
        return
    push_view(page, build_staff_view(page, records, record, route))
