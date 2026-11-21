"""应用入口：页面配置与路由。"""

from __future__ import annotations

import asyncio
import inspect

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import FONT_ASSETS, app_theme
from bangumi.ui import scroll_memory, view_state
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
from bangumi.views.favorites import favorites_view
from bangumi.views.navigation import view_cache
from bangumi.data.watched_data import (
    dedupe_record_tags,
    load_records,
    save_records,
    sync_sequel_groups,
)
from bangumi.data import prework

ROUTES = {
    "/watched": watched_view,
    "/watchlist": watchlist_view,
    "/season": season_view,
    "/favorites": favorites_view,
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

    @staticmethod
    def _skip_prev_refresh(view: object) -> bool:
        """视图声明 skip_prev_refresh 时，返回后不重建下层页面。"""
        data = getattr(view, "data", None)
        return (
            isinstance(data, dict)
            and data.get("skip_prev_refresh") is True
        )

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

    def _notify_shown(self) -> None:
        """栈顶变化后通知新栈顶视图（用于 keep_alive 页面恢复）。"""
        if not self:
            return
        top = self[-1]
        data = getattr(top, "data", None)
        handler = (
            data.get("on_shown") if isinstance(data, dict) else None
        )
        if callable(handler):
            try:
                handler()
            except Exception:
                pass

    def _notify_closed(self, views) -> None:
        """视图被移出栈时通知其清理状态（返回首页等）。"""
        for view in views:
            data = getattr(view, "data", None)
            handler = (
                data.get("on_close")
                if isinstance(data, dict)
                else None
            )
            if callable(handler):
                try:
                    handler()
                except Exception:
                    pass

    def append(self, view: ft.View) -> None:
        _attach_home_action(self._page, view)
        super().append(view)
        # 只保留栈顶控件树，下层视图卸载。
        view_cache.stash_hidden(self._page)

    def pop(self, index=-1):
        item = super().pop(index)
        view_cache.forget(item)
        view_cache.stash_hidden(self._page)
        self._notify_closed([item])
        view_state.forget(item)
        self._notify_shown()
        if (
            not self._defer_refresh
            and not self._skip_prev_refresh(item)
        ):
            self._refresh_top()
        return item

    def remove(self, item):
        super().remove(item)
        view_cache.forget(item)
        view_cache.stash_hidden(self._page)
        self._notify_closed([item])
        view_state.forget(item)
        self._notify_shown()
        if (
            not self._defer_refresh
            and not self._skip_prev_refresh(item)
        ):
            self._refresh_top()

    def __delitem__(self, index):
        # 记录被删区间里的最后一个视图，用于判断是否跳过刷新。
        if isinstance(index, slice):
            removed = self[index]
            last = removed[-1] if removed else None
        else:
            removed = [self[index]]
            last = self[index]
        super().__delitem__(index)
        for view in removed:
            view_cache.forget(view)
        view_cache.stash_hidden(self._page)
        self._notify_closed(removed)
        for view in removed:
            view_state.forget(view)
        self._notify_shown()
        if (
            not self._defer_refresh
            and not self._skip_prev_refresh(last)
        ):
            self._refresh_top()

    def clear(self) -> None:
        # 清空栈时同步丢弃所有暂存与页面状态。
        for view in list(self):
            view_cache.forget(view)
            view_state.forget(view)
        super().clear()

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
        # 临时构造的 View 不留在栈中，同步丢弃其页面状态。
        view_state.forget(new_view)
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
    records: list = []
    try:
        records = load_records()
        changed = sync_sequel_groups(records)
        if dedupe_record_tags(records):
            changed = True
        if changed:
            save_records(records)
    except Exception:
        pass

    try:
        prework.precompute(records)
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
        # 先按栈顶同步 resize 订阅，再与重建结果一起下发。
        from bangumi.views.navigation.stack import (
            sync_resize_subscription as _sync_resize,
        )

        _sync_resize(page)
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
        from bangumi.views.navigation.stack import (
            sync_resize_subscription,
        )

        # 先同步订阅，再与视图移除在同一次 update 中下发。
        sync_resize_subscription(page)
        page.update()
        scroll_memory.prune(page)
        scroll_memory.schedule_restore(page)
        end = getattr(page.views, "end_defer", None)
        if callable(end):
            end()

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    resize_state = {
        "compact": is_compact_layout(page),
        "token": 0,
    }

    def on_resize(event=None) -> None:
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
        # 布局真正更新前再清一次，覆盖松手后才出现的 tooltip。
        from bangumi.ui.interaction import hide_all_labels

        try:
            hide_all_labels(page)
        except Exception:
            pass
        data = getattr(top, "data", None)
        if isinstance(data, dict) and data.get("no_compact_rebuild"):
            return
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
        try:
            hide_all_labels(page)
        except Exception:
            pass

    # 全局 compact 逻辑作为 base；轻量记录最新尺寸供页面布局使用。
    page._resize_base = on_resize
    last_size = {
        "w": float(page.width or 0),
        "h": float(page.height or 0),
    }

    def _record_size(event) -> None:
        w = getattr(event, "width", None)
        h = getattr(event, "height", None)
        if isinstance(w, (int, float)):
            last_size["w"] = float(w)
        if isinstance(h, (int, float)):
            last_size["h"] = float(h)
        # 尝试同步回 page；不允许赋值时仍以记录值为准。
        try:
            if isinstance(w, (int, float)):
                page.width = float(w)
            if isinstance(h, (int, float)):
                page.height = float(h)
        except Exception:
            pass

    page.on_resize = _record_size
    page._resize_last_size = last_size

    async def poll_resize() -> None:
        """轮询窗口尺寸；停手 120ms 后按栈顶分发一次。"""
        def latest_size() -> tuple[float, float]:
            size = getattr(page, "_resize_last_size", None)
            if isinstance(size, dict) and size.get("w"):
                return (
                    float(size["w"]),
                    float(size.get("h") or 0),
                )
            return (
                float(page.width or 0),
                float(page.height or 0),
            )

        last = latest_size()
        pending = last
        changed_at = 0.0
        applied = last
        silent_until = 0.0
        while True:
            await asyncio.sleep(0.1)
            now = asyncio.get_running_loop().time()
            current = latest_size()
            if now < silent_until:
                # 分发后的静默期：只记录尺寸，避免重建反馈被当成缩放。
                last = current
                pending = current
                continue
            if silent_until:
                # 静默结束：对齐到当前尺寸。
                silent_until = 0.0
                last = current
                pending = current
                applied = current
                continue
            if current != last:
                # 只有真的不同才判断容差，避免吞掉待分发尺寸。
                if (
                    abs(current[0] - last[0]) < 2
                    and abs(current[1] - last[1]) < 2
                ):
                    last = current
                    continue
                last = current
                pending = current
                changed_at = now
                continue
            if pending != applied and now - changed_at >= 0.12:
                applied = pending
                from bangumi.views.navigation.stack import (
                    dispatch_resize,
                )

                try:
                    dispatch_resize(page, None)
                except Exception:
                    # 单个 handler 出错不应中断轮询。
                    pass
                # 分发后进入 0.35s 静默期。
                silent_until = now + 0.35

    try:
        page.run_task(poll_resize)
    except RuntimeError:
        pass

    route_change()
