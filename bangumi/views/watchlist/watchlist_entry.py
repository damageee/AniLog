"""单条已追条目的详情页。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    scroll_page,
)
from bangumi.views.widgets.toast import copy_text


def build_watchlist_detail_view(
    page: ft.Page,
    name: str,
    *,
    on_finish: Callable[[], None],
    on_drop: Callable[[], None],
    route: str,
) -> ft.View:
    """Build the 在追 page with 追完 / 不追 actions."""
    foreground = foreground_color(page)
    button_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.symmetric(horizontal=28, vertical=16),
    )
    view = ft.View(
        route=route,
        appbar=ft.AppBar(title=ui_text("在追")),
        padding=page_padding(),
        controls=[
            scroll_page(
                [
                    ft.Column(
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),
                        spacing=36,
                        controls=[
                            ft.Container(
                                alignment=ft.Alignment.CENTER,
                                width=max(
                                    200,
                                    (page.width or 1000) - 48,
                                ),
                                padding=ft.Padding.symmetric(
                                    horizontal=12
                                ),
                                on_click=lambda event: page.run_task(
                                    copy_text,
                                    page,
                                    name,
                                    "已复制动画名到剪贴板",
                                ),
                                content=ui_text(
                                    name,
                                    size=24,
                                    color=foreground,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ),
                            ft.Column(
                                horizontal_alignment=(
                                    ft.CrossAxisAlignment.CENTER
                                ),
                                spacing=20,
                                controls=[
                                    ft.Button(
                                        content=ui_text(
                                            "追完",
                                            size=18,
                                            color=ft.Colors.WHITE,
                                        ),
                                        bgcolor=ft.Colors.GREEN,
                                        style=button_style,
                                        on_click=lambda event: on_finish(),
                                    ),
                                    ft.Button(
                                        content=ui_text(
                                            "不追",
                                            size=18,
                                            color=ft.Colors.WHITE,
                                        ),
                                        bgcolor=ft.Colors.RED,
                                        style=button_style,
                                        on_click=lambda event: on_drop(),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ]
            ),
        ],
    )
    view.data = {
        "rebuild": lambda: build_watchlist_detail_view(
            page,
            name,
            on_finish=on_finish,
            on_drop=on_drop,
            route=route,
        )
    }
    return view
