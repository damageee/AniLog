"""视图栈操作：返回、入栈与自检。"""

from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft

from bangumi.ui import scroll_memory


_NAVIGATION_HOOKS: list[Callable[[ft.Page], None]] = []
_ROUTE_TASKS: dict[int, asyncio.Task] = {}
_ROUTE_TARGETS: dict[int, tuple[str, bool]] = {}


async def _drain_route(page: ft.Page) -> None:
    key = id(page)
    try:
        while True:
            request = _ROUTE_TARGETS.pop(key, None)
            if request is None:
                break
            route, follow_top = request
            if follow_top:
                route = (
                    str(getattr(page.views[-1], "route", "") or "")
                    if page.views
                    else ""
                )
            current = str(getattr(page, "route", "") or "")
            top_route = (
                str(getattr(page.views[-1], "route", "") or "")
                if page.views
                else ""
            )
            if not route:
                if key not in _ROUTE_TARGETS:
                    break
                continue
            if route == current:
                if route != top_route:
                    handler = getattr(page, "on_route_change", None)
                    if callable(handler):
                        try:
                            handler(None)
                        except Exception:
                            pass
                if key not in _ROUTE_TARGETS:
                    break
                continue
            try:
                await page.push_route(route)
            except RuntimeError:
                return
            except Exception:
                pass
            top_now = (
                str(getattr(page.views[-1], "route", "") or "")
                if page.views
                else ""
            )
            current_now = str(getattr(page, "route", "") or "")
            if top_now and top_now != current_now:
                _ROUTE_TARGETS[key] = ("", True)
    finally:
        _ROUTE_TASKS.pop(key, None)
        if key in _ROUTE_TARGETS:
            request_push_route(
                page,
                _ROUTE_TARGETS[key][0],
                follow_top=_ROUTE_TARGETS[key][1],
            )


def request_push_route(
    page: ft.Page,
    route: str,
    *,
    follow_top: bool = False,
) -> None:
    """合并快速连续的路由推送；follow_top=True 时同步到当前栈顶。"""
    if not route and not follow_top:
        return
    _ROUTE_TARGETS[id(page)] = (route, follow_top)
    task = _ROUTE_TASKS.get(id(page))
    if task is not None and not task.done():
        return
    if not _can_schedule(page):
        return
    try:
        _ROUTE_TASKS[id(page)] = page.run_task(_drain_route, page)
    except RuntimeError:
        _ROUTE_TARGETS.pop(id(page), None)


def request_sync_route(page: ft.Page) -> None:
    """把 page.route 同步到当前栈顶 View 的 route。"""
    request_push_route(page, "", follow_top=True)


def _can_schedule(page: ft.Page) -> bool:
    session = getattr(page, "session", None)
    connection = getattr(session, "connection", None) if session else None
    loop = getattr(connection, "loop", None) if connection else None
    return loop is not None and not loop.is_closed()


def register_navigation_hook(hook: Callable[[ft.Page], None]) -> None:
    if hook not in _NAVIGATION_HOOKS:
        _NAVIGATION_HOOKS.append(hook)


def _run_navigation_hooks(page: ft.Page) -> None:
    for hook in tuple(_NAVIGATION_HOOKS):
        try:
            hook(page)
        except Exception:
            pass


def go_back(
    page: ft.Page,
    route: str,
    before: Callable[[], None] | None = None,
) -> None:
    """按路由关闭当前页面，而不是按 View 身份。"""
    _run_navigation_hooks(page)
    if before is not None:
        before()
    if len(page.views) <= 1:
        page.update()
        return
    target = None
    for index in range(len(page.views) - 1, -1, -1):
        if getattr(page.views[index], "route", "") == route:
            target = index
            break
    if target is None:
        page.update()
        return
    defer = getattr(page.views, "defer_refresh", None)
    if callable(defer):
        defer()
    if target == len(page.views) - 1:
        page.views.pop()
    else:
        del page.views[target + 1:]
    page.update()
    scroll_memory.prune(page)
    scroll_memory.schedule_restore(page)
    end = getattr(page.views, "end_defer", None)
    if callable(end):
        end()


def push_view(
    page: ft.Page,
    view: ft.View,
    *,
    rebuild=None,
) -> None:
    """统一入栈：可选注册刷新回调，再 append + update。"""
    if rebuild is not None:
        data = view.data if isinstance(view.data, dict) else {}
        data["rebuild"] = rebuild
        view.data = data
    _run_navigation_hooks(page)
    page.views.append(view)
    page.update()


def audit_views(page: ft.Page) -> list[str]:
    """返回没有 rebuild 的非首页路由，方便排查遗漏。"""
    missing: list[str] = []
    for view in page.views:
        route = str(getattr(view, "route", "") or "")
        if route in ("", "/"):
            continue
        data = getattr(view, "data", None)
        if not (
            isinstance(data, dict)
            and callable(data.get("rebuild"))
        ):
            missing.append(route)
    return missing
