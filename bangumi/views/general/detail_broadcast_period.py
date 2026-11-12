"""以季度作品列表为载体的放送时间段页面。"""

from __future__ import annotations

import flet as ft

from bangumi.data.watched_data import Record
from bangumi.views.general.detail_quarter_works import (
    build_quarter_works_view,
    open_quarter_works_page,
)


def build_broadcast_period_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
    **kwargs,
) -> ft.View | None:
    """将时间段渲染为其季度作品列表的薄封装。"""
    return build_quarter_works_view(
        page,
        records,
        clicked,
        route,
        **kwargs,
    )


def open_broadcast_period_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    value: str | None = None,
) -> None:
    """打开某个放送时间段的季度作品列表。"""
    open_quarter_works_page(page, records, record, value=value)
