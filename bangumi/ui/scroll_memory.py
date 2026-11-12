"""为仍留在视图栈中的视图提供按路由记忆滚动位置。"""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft

from bangumi.ui.interaction import is_attached

_MEMORY: dict[str, dict[str, dict[str, Any]]] = {}
_PENDING: set[tuple[int, str]] = set()


def _route_in_views(page: ft.Page, route: str) -> bool:
    return any(
        str(getattr(view, "route", "") or "") == route
        for view in page.views
    )


def remember(
    page: ft.Page,
    route: str,
    key: str,
    control: Any,
) -> None:
    if not route or control is None:
        prune(page)
        return
    page_key = (id(page), route)
    if _route_in_views(page, route):
        _PENDING.discard(page_key)
    elif page_key not in _PENDING:
        _MEMORY.pop(route, None)
        _PENDING.add(page_key)
    prune(page, keep=route)
    route_state = _MEMORY.setdefault(route, {})
    previous = route_state.get(key)
    offset = 0.0
    if isinstance(previous, dict):
        try:
            offset = float(previous.get("offset", 0.0) or 0.0)
        except (TypeError, ValueError):
            offset = 0.0
    route_state[key] = {"control": control, "offset": offset}
    if getattr(control, "_scroll_memory_bound", False):
        return
    original = getattr(control, "on_scroll", None)

    def on_scroll(event: ft.OnScrollEvent) -> None:
        state = _MEMORY.get(route)
        if state is not None:
            record = state.get(key)
            if record is not None:
                record["offset"] = float(
                    getattr(event, "pixels", 0) or 0
                )
        if callable(original):
            original(event)

    control.on_scroll = on_scroll
    control._scroll_memory_bound = True


def prune(page: ft.Page, *, keep: str | None = None) -> None:
    routes = {
        str(getattr(view, "route", "") or "")
        for view in page.views
    }
    for route in list(_MEMORY):
        if route in routes or route == keep:
            continue
        _MEMORY.pop(route, None)
    page_id = id(page)
    for pending in list(_PENDING):
        if pending[0] != page_id:
            continue
        pending_route = pending[1]
        if pending_route in routes or pending_route == keep:
            continue
        _PENDING.discard(pending)


async def restore(
    page: ft.Page,
    view: ft.View | None = None,
) -> None:
    await asyncio.sleep(0.12)
    prune(page)
    if not page.views:
        return
    target = view if view is not None else page.views[-1]
    if target not in page.views:
        return
    route = str(getattr(target, "route", "") or "")
    records = _MEMORY.get(route)
    if not records:
        return
    for record in tuple(records.values()):
        control = record.get("control")
        try:
            offset = float(record.get("offset", 0) or 0)
        except (TypeError, ValueError):
            offset = 0.0
        if offset <= 0 or not is_attached(control):
            continue
        try:
            await control.scroll_to(offset=offset, duration=0)
        except Exception:
            pass


def schedule_restore(
    page: ft.Page,
    view: ft.View | None = None,
) -> None:
    page.run_task(restore, page, view)
