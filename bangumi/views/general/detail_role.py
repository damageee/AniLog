"""从观影表格打开的角色列表页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.navigation import ROLE, open_detail
from bangumi.views.widgets.links import RoleLine
from bangumi.data.role_core import (
    first_role_name,
    parse_roles,
    role_lines,
)
from bangumi.data.watched_data import Record, load_records

__all__ = [
    "build_role_view",
    "first_role_name",
    "parse_roles",
    "role_lines",
]


def build_role_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    anime = str(clicked.get("anime", "") or "").strip()
    foreground = foreground_color(page)
    entries = [
        (name, cvs)
        for name, cvs in parse_roles(
            str(clicked.get("role", "") or "")
        )
        if name
    ]
    items: list[ft.Control] = [
        RoleLine(
            page,
            records,
            clicked,
            name=name,
            cvs=cvs,
            size=14,
            color=foreground,
            copy_role=True,
        )
        for name, cvs in entries
    ]
    if not items:
        items = [ui_text("", size=14, color=foreground)]

    view = ft.View(
        route=route,
        appbar=ft.AppBar(
            title=ui_text(
                f"{anime}（角色）",
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ),
        padding=page_padding(),
        controls=[
            vertical_page(
                [ft.Column(spacing=4, controls=items)]
            )
        ],
    )
    view.data = {
        "rebuild": lambda: build_role_view(
            page, load_records(), clicked, route
        )
    }
    return view


def open_role_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    value: str | None = None,
) -> None:
    """打开某条记录的角色列表页。"""
    open_detail(page, records, record, ROLE, value=value)
