"""从角色行打开的声优详情页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.interaction import (
    hover_copy,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.navigation import CAST, ENTRY, open_detail
from bangumi.views.widgets.links import DetailLink
from bangumi.data.role_core import cast_names, cast_roles
from bangumi.data.quarter_core import sort_records_by_broadcast
from bangumi.views.widgets.toast import copy_text, copyable_title
from bangumi.data.watched_data import Record, load_records


def _roles_text(
    page: ft.Page,
    roles: list[str],
    foreground: str,
) -> ft.Control:
    if not roles:
        return ui_text(
            "",
            size=14,
            color=foreground,
            text_align=ft.TextAlign.RIGHT,
        )

    parts: list[ft.Control] = []
    for index, role in enumerate(roles):
        if index:
            parts.append(
                ui_text("、", size=14, color=foreground)
            )
        parts.append(
            hover_copy(
                page,
                ui_text(
                    role,
                    size=14,
                    color=foreground,
                    no_wrap=False,
                ),
                (
                    lambda event, value=role: page.run_task(
                        copy_text,
                        page,
                        value,
                        "已复制角色名到剪贴板",
                    )
                ),
            )
        )
    return ft.Row(
        wrap=True,
        spacing=0,
        run_spacing=2,
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=parts,
    )


def build_cast_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    cast = str(clicked.get("cast", "") or "").strip()
    ordered = sort_records_by_broadcast(records)

    rows: list[tuple[Record, list[str]]] = []
    for record in ordered:
        text = str(record.get("role", "") or "")
        if cast not in cast_names(text):
            continue
        anime = str(record.get("anime", "") or "").strip()
        if not anime:
            continue
        roles: list[str] = []
        for role in cast_roles(text, cast):
            if role not in roles:
                roles.append(role)
        rows.append((record, roles))

    foreground = foreground_color(page)
    items: list[ft.Control] = []
    for record, roles in rows:
        items.append(
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        expand=2,
                        alignment=ft.Alignment.CENTER_RIGHT,
                        content=_roles_text(
                            page,
                            roles,
                            foreground,
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
    if not items:
        items = [ui_text("", size=14, color=foreground)]

    view = ft.View(
        route=route,
        appbar=ft.AppBar(
            title=copyable_title(page, cast or "声优"),
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
                                    controls=items,
                                ),
                            )
                        ],
                    )
                ]
            )
        ],
    )
    view.data = {
        "rebuild": lambda: build_cast_view(
            page, load_records(), clicked, route
        )
    }
    return view


def open_cast_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    value: str | None = None,
) -> None:
    """打开某位声优的共用 CAST 页面。"""
    open_detail(page, records, record, CAST, value=value)
