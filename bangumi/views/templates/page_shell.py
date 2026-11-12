"""页面外壳模板：滚动、返回箭头与刷新钩子。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui import scroll_memory
from bangumi.ui.interaction import back_icon
from bangumi.ui.layout import page_padding, scroll_page


def make_view(
    page: ft.Page,
    *,
    route: str,
    title: str,
    controls: list[ft.Control],
    rebuild: Callable[[], ft.View] | None = None,
    before: Callable[[], None] | None = None,
    back: bool = False,
    scroll: bool = True,
    padding: ft.Padding | None = None,
    appbar: ft.AppBar | None = None,
    spacing: int = 10,
) -> ft.View:
    """构建带滚动、可选返回箭头与刷新钩子的页面。"""
    if appbar is None:
        appbar = ft.AppBar(
            title=ui_text(title),
            automatically_imply_leading=not back,
        )
        if back:
            appbar.leading = back_icon(page, route, before=before)
    column: ft.Control | None = None
    if scroll:
        column = scroll_page(controls, spacing=spacing)
        content = [column]
    else:
        content = controls
    view = ft.View(
        route=route,
        appbar=appbar,
        padding=padding or page_padding(),
        controls=content,
    )
    if column is not None:
        scroll_memory.remember(page, route, "page", column)
    if rebuild is not None:
        view.data = {"rebuild": rebuild}
    scroll_memory.schedule_restore(page, view)
    return view
