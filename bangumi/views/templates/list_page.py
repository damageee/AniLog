"""通用列表页：逐行名称 + 点击打开条目页。"""

from __future__ import annotations

from typing import Callable

import flet as ft
from bangumi.ui.events import is_hover

from bangumi.ui.theme import ui_text
from bangumi.ui.interaction import (
    back_icon,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
)
from bangumi.views.navigation import (
    push_view,
)
from bangumi.views.navigation import ENTRY
from bangumi.views.navigation import open_detail
from bangumi.views.widgets.toast import copyable_title
from bangumi.ui.constants import (
    HOVER_ROW_OPACITY,
    TABLE_LINE_OPACITY,
)
from bangumi.data.watched_data import Record


def build_list_view(
    page: ft.Page,
    *,
    title: str,
    route: str,
    entries: list[tuple[str, Record]],
    records: list[Record],
    before: Callable[[], None] | None = None,
    rebuild: Callable[[], ft.View] | None = None,
    tooltip: str = "打开条目页",
    copy_title: bool = False,
) -> ft.View:
    text_color = foreground_color(page)
    hover_color = ft.Colors.with_opacity(
        HOVER_ROW_OPACITY, text_color
    )
    controls: list[ft.Control] = []
    for text, record in entries:
        def on_click(
            event: ft.ControlEvent,
            target: Record = record,
        ) -> None:
            open_entry_with_back(
                page,
                records,
                target,
                before=before,
            )

        row = ft.Container(
            padding=ft.Padding.symmetric(horizontal=6, vertical=9),
            border_radius=6,
            border=ft.Border(
                bottom=ft.BorderSide(
                    1,
                    ft.Colors.with_opacity(
                        TABLE_LINE_OPACITY,
                        text_color,
                    ),
                )
            ),
            on_click=on_click,
            tooltip=tooltip,
            content=ui_text(text, size=15),
        )

        def on_hover(
            event: ft.ControlEvent,
            container: ft.Container = row,
        ) -> None:
            hovered = is_hover(event)
            container.bgcolor = hover_color if hovered else None
            container.update()

        row.on_hover = on_hover
        controls.append(row)
    if not controls:
        controls.append(ui_text("暂无数据", size=15))

    view = ft.View(
        route=route,
        appbar=ft.AppBar(
            title=(
                copyable_title(page, title)
                if copy_title
                else ui_text(title)
            ),
            automatically_imply_leading=False,
            leading=back_icon(page, route, before=before),
        ),
        padding=page_padding(),
        controls=[
            ft.ListView(
                expand=True,
                spacing=0,
                controls=controls,
            )
        ],
    )
    if rebuild is not None:
        view.data = {"rebuild": rebuild}
    return view


def open_list_page(
    page: ft.Page,
    *,
    title: str,
    route: str,
    entries: list[tuple[str, Record]],
    records: list[Record],
    before: Callable[[], None] | None = None,
    rebuild: Callable[[], ft.View] | None = None,
) -> None:
    if page.views and getattr(page.views[-1], "route", "") == route:
        return
    push_view(
        page,
        build_list_view(
            page,
            title=title,
            route=route,
            entries=entries,
            records=records,
            before=before,
            rebuild=rebuild,
        ),
    )


def open_entry_with_back(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    before: Callable[[], None] | None = None,
) -> None:
    open_detail(page, records, record, ENTRY)
    if not page.views:
        return
    entry_view = page.views[-1]
    appbar = getattr(entry_view, "appbar", None)
    if appbar is None:
        return
    entry_route = str(getattr(entry_view, "route", "") or "")

    appbar.automatically_imply_leading = False
    appbar.leading = back_icon(page, entry_route, before=before)
    try:
        entry_view.update()
    except Exception:
        page.update()
