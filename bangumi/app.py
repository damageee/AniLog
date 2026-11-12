"""应用入口：页面配置与路由。"""

from __future__ import annotations

import asyncio
import inspect

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import FONT_ASSETS, app_theme
from bangumi.ui import scroll_memory
from bangumi.ui.interaction import (
    hover_icon,
    scroll_bottom_action,
    SCROLL_BOTTOM_MARKER,
)
from bangumi.views import (
    home_view,
    season_view,
    settings_view,
    statistics_view,
    watched_view,
    watchlist_view,
)
from bangumi.data.watched_data import (
    dedupe_record_tags,
    load_records,
    save_records,
    sync_sequel_groups,
)

ROUTES = {
    "/watched": watched_view,
    "/watchlist": watchlist_view,
    "/season": season_view,
    "/statistics": statistics_view,
    "/settings": settings_view,
}


async def _go_home(page: ft.Page) -> None:
    if len(page.views) > 1:
        del page.views[1:]
        page.update()


def _attach_home_action(page: ft.Page, view: ft.View) -> None:
    route = str(getattr(view, "route", "") or "")
    if route == "/":
        return
    appbar = getattr(view, "appbar", None)
    if appbar is None:
        return
    actions = list(getattr(appbar, "actions", None) or [])

    def is_home(action) -> bool:
        if getattr(action, "tooltip", "") == "返回首页":
            return True
        content = getattr(action, "content", None)
        return getattr(content, "tooltip", "") == "返回首页"

    def is_scroll(action) -> bool:
        data = getattr(action, "data", None)
        if data is None:
            data = getattr(getattr(action, "content", None), "data", None)
        return data == SCROLL_BOTTOM_MARKER

    changed = False
    home_index = next(
        (index for index, action in enumerate(actions) if is_home(action)),
        None,
    )
    if not any(is_scroll(action) for action in actions):
        button = scroll_bottom_action(page, view)
        if button is not None:
            position = home_index if home_index is not None else len(actions)
            actions.insert(position, button)
            changed = True

    if home_index is None:
        actions.append(
            ft.Container(
                padding=ft.Padding.only(right=16),
                content=hover_icon(
                    page,
                    ft.Icons.HOME_OUTLINED,
                    size=20,
                    padding=8,
                    tooltip="返回首页",
                    on_click=lambda event: page.run_task(
                        _go_home,
                        page,
                    ),
                ),
            )
        )
        changed = True

    if changed:
        appbar.actions = actions


def _ensure_rebuild(
    page: ft.Page,
    view: ft.View,
    builder,
) -> None:
    data = getattr(view, "data", None)
    if not isinstance(data, dict):
        data = {}
        view.data = data
    if callable(data.get("rebuild")):
        return

    def rebuild() -> ft.View:
        view = builder(page)
        _ensure_rebuild(page, view, builder)
        return view

    data["rebuild"] = rebuild


class _HomeIconViews(list):
    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self._page = page
        self._refreshing = False
        self._defer_refresh = False

    def defer_refresh(self) -> None:
        self._defer_refresh = True

    def end_defer(self) -> None:
        """结束延迟刷新，不触发重建。"""
        self._defer_refresh = False

    def flush_refresh(self) -> None:
        if not self._defer_refresh:
            return
        self._defer_refresh = False
        self._refresh_top()

    def append(self, view: ft.View) -> None:
        _attach_home_action(self._page, view)
        super().append(view)

    def pop(self, index=-1):
        item = super().pop(index)
        if not self._defer_refresh:
            self._refresh_top()
        return item

    def remove(self, item):
        super().remove(item)
        if not self._defer_refresh:
            self._refresh_top()

    def __delitem__(self, index):
        super().__delitem__(index)
        if not self._defer_refresh:
            self._refresh_top()

    def _refresh_top(self) -> None:
        if self._refreshing or not self:
            return
        top = self[-1]
        data = getattr(top, "data", None)
        if not isinstance(data, dict):
            return

        refresh = data.get("refresh")
        if callable(refresh):
            self._refreshing = True
            try:
                refresh()
            except Exception:
                pass
            finally:
                self._refreshing = False
            self._page.update()
            scroll_memory.schedule_restore(self._page)
            return

        builder = data.get("rebuild")
        if not callable(builder):
            return
        self._refreshing = True
        try:
            new_view = builder()
        except Exception:
            new_view = None
        finally:
            self._refreshing = False
        if new_view is None:
            return
        # 不要替换 self[-1]：Flet 对同索引 View 交换的 diff
        # 不可靠。应改为就地更新已挂载 View 的字段。
        _attach_home_action(self._page, new_view)
        old_appbar = getattr(top, "appbar", None)
        new_appbar = getattr(new_view, "appbar", None)
        if old_appbar is not None and new_appbar is not None:
            old_appbar.title = new_appbar.title
            old_appbar.actions = new_appbar.actions
        else:
            top.appbar = new_appbar
        top.controls = new_view.controls
        top.padding = new_view.padding
        if isinstance(new_view.data, dict):
            data.update(new_view.data)
            top.data = data
        self._page.update()
        scroll_memory.schedule_restore(self._page)


async def _await_awaitable(value) -> None:
    await value


def _chain_keyboard_handler(page: ft.Page, handler, event) -> None:
    if handler is None:
        return
    result = handler(event)
    if inspect.isawaitable(result):
        page.run_task(_await_awaitable, result)


async def _escape_back(page: ft.Page) -> None:
    """点击顶层视图的返回箭头；不可用时退回通用返回。"""
    if len(page.views) <= 1:
        return
    appbar = getattr(page.views[-1], "appbar", None)
    leading = (
        getattr(appbar, "leading", None)
        if appbar is not None
        else None
    )
    handler = (
        getattr(leading, "on_click", None)
        if leading is not None
        else None
    )
    if callable(handler):
        try:
            result = handler(None)
            if inspect.isawaitable(result):
                await result
            return
        except Exception:
            pass

    defer = getattr(page.views, "defer_refresh", None)
    if callable(defer):
        defer()
    page.views.pop()
    page.update()
    end = getattr(page.views, "end_defer", None)
    if callable(end):
        end()


def _has_open_dialog(page: ft.Page) -> bool:
    """仅当确有对话框打开时返回 True。"""
    dialogs = getattr(page, "_dialogs", None)
    controls = getattr(dialogs, "controls", None)
    if not controls:
        return False
    return any(
        bool(getattr(dialog, "open", False)) for dialog in controls
    )


def install_escape_back(page: ft.Page) -> None:
    """将 Esc 路由到与顶层视图返回箭头相同的动作。"""
    previous_keyboard = page.on_keyboard_event
    if getattr(previous_keyboard, "_escape_back_hook", False):
        return

    def on_keyboard_event(event: ft.KeyboardEvent) -> None:
        key = str(getattr(event, "key", "") or "")
        if key in ("Escape", "Esc"):
            if _has_open_dialog(page):
                _chain_keyboard_handler(
                    page, previous_keyboard, event
                )
                return
            if bool(getattr(event, "shift", False)):
                page.run_task(_go_home, page)
                return
            page.run_task(_escape_back, page)
            return
        _chain_keyboard_handler(page, previous_keyboard, event)

    on_keyboard_event._escape_back_hook = True
    page.on_keyboard_event = on_keyboard_event


def main(page: ft.Page) -> None:
    try:
        records = load_records()
        changed = sync_sequel_groups(records)
        if dedupe_record_tags(records):
            changed = True
        if changed:
            save_records(records)
    except Exception:
        pass

    preferences = Preferences.load()
    page.title = "AniLog"
    page.fonts = FONT_ASSETS
    page.theme = app_theme()
    page.dark_theme = app_theme(dark=True)

    dark_mode = preferences.theme_mode == "dark"
    page.theme_mode = (
        ft.ThemeMode.DARK if dark_mode else ft.ThemeMode.LIGHT
    )
    page.bgcolor = ft.Colors.BLACK if dark_mode else ft.Colors.WHITE
    if page.platform == ft.PagePlatform.WINDOWS:
        page.window.icon = "/pic/icon.ico"

    page.views = _HomeIconViews(page)

    views_initialized = False

    def route_change(event: ft.RouteChangeEvent | None = None) -> None:
        nonlocal views_initialized

        if event is not None:
            event_route = getattr(event, "route", None)
            if event_route and event_route != page.route:
                return

        # Flet 启动时可能已包含一个空白默认视图。仅当本应用
        # 确实填充过视图栈后，才跳过重建。
        if (
            views_initialized
            and page.views
            and page.views[-1].route == page.route
        ):
            try:
                page.update()
            except RuntimeError:
                return
            return

        # 路由已经在栈中（常见于嵌套路由返回）：只裁剪到该视图，
        # 不要清空重建，否则会退回首页并闪 Working。
        for index in range(len(page.views) - 1, -1, -1):
            view_route = str(
                getattr(page.views[index], "route", "") or ""
            )
            if view_route == page.route:
                if index != len(page.views) - 1:
                    del page.views[index + 1:]
                    try:
                        page.update()
                    except RuntimeError:
                        pass
                return

        builder = ROUTES.get(page.route)
        if builder is None and page.views:
            # 路由已不在 ROUTES（嵌套页）且不在当前栈中：
            # 视为快速导航产生的陈旧事件，不要清空重建，也不要再推路由。
            return

        page.views.clear()
        page.views.append(home_view(page))
        if builder is not None:
            view = builder(page)
            _ensure_rebuild(page, view, builder)
            page.views.append(view)
        views_initialized = True
        try:
            page.update()
        except RuntimeError:
            return

    async def view_pop(event: ft.ViewPopEvent) -> None:
        defer = getattr(page.views, "defer_refresh", None)
        if callable(defer):
            defer()
        if event.view is not None and event.view in page.views:
            page.views.remove(event.view)
        page.update()
        scroll_memory.prune(page)
        scroll_memory.schedule_restore(page)
        end = getattr(page.views, "end_defer", None)
        if callable(end):
            end()

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    route_change()

    previous_resize = page.on_resize
    resize_state = {
        "compact": is_compact_layout(page),
        "token": 0,
    }

    def on_resize(event=None) -> None:
        if (
            previous_resize is not None
            and previous_resize is not on_resize
        ):
            previous_resize(event)
        current = is_compact_layout(page)
        if current == resize_state["compact"]:
            return
        resize_state["compact"] = current
        resize_state["token"] += 1
        page.run_task(apply_resize, resize_state["token"])

    async def apply_resize(token: int) -> None:
        if token != resize_state["token"] or not page.views:
            return
        top = page.views[-1]
        top_route = str(getattr(top, "route", "") or "")
        await asyncio.sleep(0.15)
        if token != resize_state["token"] or not page.views:
            return
        if str(getattr(page.views[-1], "route", "") or "") != top_route:
            return
        data = getattr(top, "data", None)
        if isinstance(data, dict) and callable(data.get("rebuild")):
            try:
                new_view = data["rebuild"]()
                _attach_home_action(page, new_view)
            except Exception:
                new_view = None
            if new_view is not None:
                try:
                    top.controls = new_view.controls
                    top.appbar = new_view.appbar
                    top.padding = new_view.padding
                    if isinstance(new_view.data, dict):
                        data.update(new_view.data)
                except Exception:
                    pass
        try:
            page.update()
        except RuntimeError:
            return

    page.on_resize = on_resize
