"""列出带有某个标签的动画的 TAG 详情页。"""

from __future__ import annotations

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.ui.theme import ui_text
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.navigation import ENTRY, TAG, open_detail
from bangumi.views.widgets.links import DetailLink, TagChips
from bangumi.data.quarter_core import sort_records_by_broadcast
from bangumi.data.watched_data import Record, load_records, split_tags


def build_tag_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    tag = str(clicked.get("tag", "") or "").strip()
    matches = [
        record
        for record in records
        if tag in split_tags(record.get("tag", ""))
    ]
    matches = sort_records_by_broadcast(matches)
    tag_colors = Preferences.load().tag_colors
    foreground = foreground_color(page)
    rows: list[ft.Control] = []
    for record in matches:
        rows.append(
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        expand=2,
                        alignment=ft.Alignment.CENTER_RIGHT,
                        content=TagChips(
                            page,
                            records,
                            record,
                            tag_colors,
                            size=12,
                            wrap=True,
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ),
                    ft.Container(
                        width=1,
                        height=20,
                        bgcolor=ft.Colors.with_opacity(
                            0.25,
                            foreground,
                        ),
                    ),
                    ft.Container(
                        expand=3,
                        alignment=ft.Alignment.CENTER_LEFT,
                        content=DetailLink(
                            page,
                            records,
                            record,
                            ENTRY,
                            text=str(
                                record.get("anime", "") or ""
                            ).strip(),
                            size=14,
                            color=foreground,
                        ),
                    ),
                ],
            )
        )
    if not rows:
        rows = [ui_text("", size=14, color=foreground)]

    view = ft.View(
        route=route,
        appbar=ft.AppBar(
            title=ui_text(
                tag or "TAG",
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.ResponsiveRow(
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Container(
                                col={
                                    "xs": 12,
                                    "sm": 12,
                                    "md": 10,
                                    "lg": 8,
                                    "xl": 8,
                                },
                                content=ft.Column(
                                    spacing=4,
                                    horizontal_alignment=(
                                        ft.CrossAxisAlignment.STRETCH
                                    ),
                                    controls=rows,
                                ),
                            )
                        ],
                    )
                ]
            )
        ],
    )
    view.data = {
        "rebuild": lambda: build_tag_view(
            page, load_records(), clicked, route
        )
    }
    return view


def open_tag_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    value: str | None = None,
) -> None:
    """打开某个标签的 TAG 详情页。"""
    open_detail(page, records, record, TAG, value=value)
