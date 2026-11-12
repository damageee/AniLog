"""记录哪些路由已经播放过入场动画。"""

from __future__ import annotations

import flet as ft

_SEEN: set[str] = set()


def prune(page: ft.Page) -> None:
    routes = {
        str(getattr(view, "route", "") or "")
        for view in page.views
    }
    for route in list(_SEEN):
        if route not in routes:
            _SEEN.discard(route)


def first_entry(page: ft.Page, route: str) -> bool:
    prune(page)
    return route not in _SEEN


def mark_seen(page: ft.Page, route: str) -> None:
    _SEEN.add(route)
