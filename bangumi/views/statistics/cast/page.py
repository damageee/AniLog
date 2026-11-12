"""声优统计主页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.layout import page_padding, vertical_page
from bangumi.views.statistics.common.shared import _open_statistics_page
from .search import cast_search_view


def cast_view(page: ft.Page) -> ft.View:
    buttons = [
        ft.Button(
            content=ui_text("搜索", size=18),
            style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
            on_click=lambda event: _open_statistics_page(
                page,
                cast_search_view,
            ),
        )
    ]
    view = ft.View(
        route="/statistics/cast",
        appbar=ft.AppBar(title=ui_text("声优")),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.Column(
                        spacing=12,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.STRETCH
                        ),
                        controls=buttons,
                    )
                ]
            )
        ],
    )
    view.data = {"rebuild": lambda: cast_view(page)}
    return view
