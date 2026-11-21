"""统计主页。"""

from __future__ import annotations

from typing import (
    Callable,
)
import flet as ft
from bangumi.ui.theme import (
    ui_text,
    ui_text_style,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.ui.interaction import back_icon
from bangumi.views.statistics.broadcast import (
    broadcast_view,
)
from bangumi.views.statistics.annual import (
    annual_view,
)
from bangumi.views.statistics.cast import (
    cast_view,
)
from bangumi.views.statistics.data_check import (
    data_view,
)
from bangumi.views.statistics.journey import (
    journey_view,
)
from bangumi.views.statistics.overview import (
    overview_view,
)
from bangumi.views.statistics.rating import (
    rating_view,
)
from bangumi.views.statistics.best_records import (
    records_view,
)
from bangumi.views.statistics.coverwall import (
    coverwall_view,
)
from bangumi.views.statistics.common.shared import (
    _open_statistics_page,
)
from bangumi.views.statistics.studios import (
    studios_view,
)
from bangumi.views.statistics.staff import (
    staff_view,
)
from bangumi.views.statistics.tags import (
    tags_view,
)


def statistics_view(page: ft.Page) -> ft.View:
    buttons = [
        ft.Button(
            content=ui_text(title, size=18),
            style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
            on_click=(
                lambda event, build=builder: (
                    _open_statistics_page(page, build)
                )
            ),
        )
        for title, builder in STATISTICS_PAGES
    ]

    view = ft.View(
        route="/statistics",
        appbar=ft.AppBar(
            title=ui_text("统计"),
            automatically_imply_leading=False,
            leading=back_icon(page, "/"),
        ),
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
        "rebuild": lambda: statistics_view(page)
    }
    return view


STATISTICS_PAGES: tuple[
    tuple[str, Callable[[ft.Page], ft.View]],
    ...,
] = (
    ("总览", overview_view),
    ("放送", broadcast_view),
    ("旅途", journey_view),
    ("标签", tags_view),
    ("班底", staff_view),
    ("制作", studios_view),
    ("声优", cast_view),
    ("评分", rating_view),
    ("封面", coverwall_view),
    ("年报", annual_view),
    ("纪录", records_view),
    ("数据", data_view),
)


