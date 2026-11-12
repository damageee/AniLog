"""制作公司搜索页。"""

from __future__ import annotations

import flet as ft

from bangumi.data.watched_data import load_records
from bangumi.ui.colors import foreground_color
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.general.virtual_search import virtual_search_page
from bangumi.data.statistics.studios import studio_statistics
from bangumi.views.statistics.common.shared import _accent
from bangumi.views.widgets.links import highlight_spans
from .homepage import open_studio_page


def studio_search_view(
    page: ft.Page,
    initial_query: str = "",
) -> ft.View:
    records = load_records()
    fg = foreground_color(page)
    highlight = _accent(page, "#FDE68A", "#B45309")

    def row_builder(item, query: str) -> ft.Control:
        studio, count, _company_records = item

        def on_click(event: ft.ControlEvent) -> None:
            open_studio_page(page, records, studio)

        return ft.Container(
            height=40,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.only(
                left=6,
                right=20,
                top=0,
                bottom=0,
            ),
            border_radius=6,
            border=ft.Border(
                bottom=ft.BorderSide(
                    1,
                    ft.Colors.with_opacity(0.1, fg),
                )
            ),
            on_click=on_click,
            tooltip="打开制作公司详情",
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(
                        spans=highlight_spans(
                            studio,
                            query,
                            base_style=ui_text_style(
                                size=15, color=fg
                            ),
                            match_style=ui_text_style(
                                size=15,
                                color=fg,
                                bgcolor=highlight,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                        no_wrap=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ui_text(str(count), size=13, color=fg),
                ],
            ),
        )

    view = virtual_search_page(
        page,
        title="制作公司 —— 搜索",
        route="/statistics/studios/search",
        hint_text="搜索制作公司",
        all_rows=studio_statistics(records),
        row_builder=row_builder,
        initial_query=initial_query,
        rebuild=lambda q: studio_search_view(page, q),
    )
    return view
