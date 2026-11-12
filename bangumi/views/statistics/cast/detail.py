"""声优详情入口。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.interaction import back_icon
from bangumi.views.navigation import CAST, open_detail
from bangumi.data.watched_data import Record
from bangumi.views.statistics.common.overlays import _hide_page_overlay


def _open_cast_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    cast: str,
) -> None:
    """打开带返回列表按钮的共用 CAST 页面。"""
    open_detail(
        page,
        records,
        {**record, "cast": cast},
        CAST,
        value=cast,
    )
    if not page.views:
        return
    cast_page = page.views[-1]
    appbar = getattr(cast_page, "appbar", None)
    if appbar is None:
        return
    cast_route = str(getattr(cast_page, "route", "") or "")

    appbar.automatically_imply_leading = False
    appbar.leading = back_icon(
        page,
        cast_route,
        before=lambda: _hide_page_overlay(page),
    )
    try:
        cast_page.update()
    except Exception:
        page.update()
