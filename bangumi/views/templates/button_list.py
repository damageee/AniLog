"""通用整宽按钮列表页。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.interaction import (
    back_icon,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)


def build_button_list_view(
    page: ft.Page,
    *,
    title: str,
    route: str,
    buttons: list[tuple[str, Callable]],
    rebuild: Callable[[], ft.View] | None = None,
    back: bool = True,
    on_long_press=None,
    on_long_press_end=None,
    on_long_press_cancel=None,
    footer: ft.Control | None = None,
) -> ft.View:
    controls = [
        ft.Button(content=ui_text(label), on_click=handler)
        for label, handler in buttons
    ]
    if footer is not None:
        controls.append(ft.Container(height=4))
        controls.append(
            ft.GestureDetector(
                on_tap=lambda event: None,
                on_long_press=lambda event: None,
                on_long_press_end=lambda event: None,
                on_long_press_cancel=lambda event: None,
                content=footer,
            )
        )
    content: ft.Control = vertical_page(controls, stretch=True)
    if on_long_press is not None:
        content = ft.GestureDetector(
            expand=True,
            content=content,
            on_long_press=on_long_press,
            on_long_press_end=on_long_press_end,
            on_long_press_cancel=on_long_press_cancel,
        )
    appbar = ft.AppBar(
        title=ui_text(title),
        automatically_imply_leading=not back,
    )
    if back:
        appbar.leading = back_icon(page, route)
    view = ft.View(
        route=route,
        appbar=appbar,
        padding=page_padding(),
        controls=[content],
    )
    if rebuild is not None:
        view.data = {"rebuild": rebuild}
    return view
