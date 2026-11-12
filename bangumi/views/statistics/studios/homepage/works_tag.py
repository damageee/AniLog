"""制作公司「擅长 TAG」子页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.data.quarter_core import sort_records_by_broadcast
from bangumi.data.watched_data import (
    Record,
    load_records,
    split_studios,
    split_tags,
)
from bangumi.ui.colors import foreground_color
from bangumi.ui.layout import vertical_page
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import ENTRY, push_view
from bangumi.views.statistics.common.shared import _back_view
from bangumi.views.widgets.links import DetailLink, TagChips


def _studio_tag_view(
    page: ft.Page,
    records: list[Record],
    name: str,
    tag: str,
    company_records: list[Record],
) -> ft.View:
    route = (
        "/statistics/studios/tag/"
        + quote(name, safe="")
        + "/"
        + quote(tag, safe="")
    )
    matches = [
        record
        for record in company_records
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

    def rebuild() -> ft.View:
        fresh = load_records()
        fresh_company = [
            record
            for record in fresh
            if name in split_studios(record.get("studio"))
        ]
        return _studio_tag_view(
            page,
            fresh,
            name,
            tag,
            fresh_company,
        )

    return _back_view(
        page,
        route=route,
        title=f"{tag}（{name}）",
        controls=[
            vertical_page(
                [
                    ft.ResponsiveRow(
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=(
                            ft.CrossAxisAlignment.START
                        ),
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
        rebuild=rebuild,
    )


def _open_studio_tag(
    page: ft.Page,
    records: list[Record],
    company: str,
    tag: str,
    company_records: list[Record],
) -> None:
    name = str(company or "").strip()
    tag_name = str(tag or "").strip()
    if not name or not tag_name:
        return
    route = (
        "/statistics/studios/tag/"
        + quote(name, safe="")
        + "/"
        + quote(tag_name, safe="")
    )
    if (
        page.views
        and getattr(page.views[-1], "route", "") == route
    ):
        return
    push_view(
        page,
        _studio_tag_view(
            page,
            records,
            name,
            tag_name,
            company_records,
        ),
    )
