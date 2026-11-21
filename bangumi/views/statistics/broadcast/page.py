"""放送时间页。"""

from __future__ import annotations

import flet as ft
from bangumi.ui.theme import (
    ui_text,
    ui_text_style,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from .quarter import (
    quarter_view,
)
from bangumi.views.statistics.common.shared import (
    _open_statistics_page,
)
from .year import (
    year_view,
)


def broadcast_view(page: ft.Page) -> ft.View:
    buttons = [
        ft.Button(
            content=ui_text("年份", size=18),
            style=ft.ButtonStyle(
                text_style=ui_text_style(size=18)
            ),
            on_click=lambda event: _open_statistics_page(
                page,
                year_view,
            ),
        ),
        ft.Button(
            content=ui_text("季度", size=18),
            style=ft.ButtonStyle(
                text_style=ui_text_style(size=18)
            ),
            on_click=lambda event: _open_statistics_page(
                page,
                quarter_view,
            ),
        ),
    ]
    view = ft.View(
        route="/statistics/broadcast",
        appbar=ft.AppBar(title=ui_text("放送时间")),
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
    view.data = {
        "rebuild": lambda: broadcast_view(page)
    }
    return view


