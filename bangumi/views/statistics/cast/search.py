"""声优搜索页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.colors import foreground_color
from bangumi.data.watched_data import load_records
from bangumi.data.statistics.cast import cast_statistics
from bangumi.views.statistics.common.shared import _accent
from bangumi.views.general.virtual_search import virtual_search_page
from bangumi.views.widgets.links import highlight_spans
from .detail import _open_cast_page


def cast_search_view(
    page: ft.Page,
    initial_query: str = "",
) -> ft.View:
    records = load_records()
    fg = foreground_color(page)
    highlight = _accent(page, "#FDE68A", "#B45309")

    def row_builder(item, query: str) -> ft.Control:
        cast, count, sample = item

        def on_click(event: ft.ControlEvent) -> None:
            _open_cast_page(page, records, sample, cast)

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
            tooltip="打开声优详情",
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(
                        spans=highlight_spans(
                            cast,
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

    return virtual_search_page(
        page,
        title="声优 —— 搜索",
        route="/statistics/cast/search",
        hint_text="搜索声优",
        all_rows=cast_statistics(records),
        row_builder=row_builder,
        initial_query=initial_query,
        rebuild=lambda q: cast_search_view(page, q),
    )
