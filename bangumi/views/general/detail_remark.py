"""从观影表格打开的只读备注页。"""

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
from bangumi.data.watched_data import Record, load_records


def build_remark_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    anime = str(clicked.get("anime", "") or "").strip()
    remark = (
        str(clicked.get("remark", "") or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    foreground = foreground_color(page)
    lines = remark.split("\n")
    items: list[ft.Control] = [
        ui_text(line, size=14, color=foreground)
        for line in lines
    ]
    if not items:
        items = [ui_text("", size=14, color=foreground)]

    view = ft.View(
        route=route,
        appbar=ft.AppBar(
            title=ui_text(
                f"{anime}（备注）",
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ),
        padding=page_padding(),
        controls=[vertical_page([ft.Column(spacing=4, controls=items)])],
    )
    view.data = {
        "rebuild": lambda: build_remark_view(
            page, load_records(), clicked, route
        )
    }
    return view


