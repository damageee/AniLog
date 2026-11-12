"""制作公司统计入口页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.layout import vertical_page
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.statistics.common.shared import _open_statistics_page
from bangumi.views.templates.page_shell import make_view
from .honor import honor_view
from .scatter import studio_scatter_view
from .search import studio_search_view


def studios_view(page: ft.Page) -> ft.View:
    buttons = [
        ft.Button(
            content=ui_text("搜索", size=18),
            style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
            on_click=lambda event: _open_statistics_page(
                page,
                studio_search_view,
            ),
        ),
        ft.Button(
            content=ui_text("荣誉榜", size=18),
            style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
            on_click=lambda event: _open_statistics_page(
                page,
                honor_view,
            ),
        ),
        ft.Button(
            content=ui_text("质量×产量", size=18),
            style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
            on_click=lambda event: _open_statistics_page(
                page,
                studio_scatter_view,
            ),
        ),
    ]
    return make_view(
        page,
        route="/statistics/studios",
        title="制作公司",
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
        rebuild=lambda: studios_view(page),
        back=True,
        scroll=False,
    )
