"""已追页面：左右两列，支持拖动排序。"""

from __future__ import annotations

import asyncio
import math
import random
import time
from urllib.parse import quote

import flet as ft
from bangumi.ui.anim import animation
import requests

from bangumi.data.preferences import Preferences
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.ui.feedback import (
    confirmation_dialog,
)
from bangumi.views.navigation import (
    go_back,
    push_view,
)
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.ui.interaction import (
    back_icon,
    hover_icon,
    hover_zoom,
)
from bangumi.ui.layout import (
    page_padding,
)
from bangumi.views.general.entry_form import open_entry_form
from bangumi.views.widgets.toast import show_toast
from bangumi.views.templates.append_from_text import build_append_from_text_view
from bangumi.views.watchlist.watchlist_entry import build_watchlist_detail_view
from bangumi.data.watchlist_data import load_watchlist, save_watchlist
from bangumi.data.watched_data import (
    Record,
    entry_group_key,
    load_records,
    propagate_sequel,
    save_records,
)

from bangumi.ui.platform import is_compact_layout
from bangumi.ui.events import is_hover, event_position
from bangumi.views.watchlist.constants import *
from bangumi.views.watchlist.layout import (
    button_width,
    divider_gap,
    list_height,
)
from bangumi.views.watchlist.utils import (
    fit_label,
    load_bilibili_uid,
    save_bilibili_uid,
)
from bangumi.services.bilibili_import import (
    BilibiliImportError,
    fetch_bilibili_following,
)
from bangumi.views.widgets.virtual_window import (
    clamp_scroll,
    max_scroll_offset,
    window_bounds,
    window_size,
)























class WatchlistPage:
    """Owns the 已追 page and its local watchlist state."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.high: list[str] = []
        self.low: list[str] = []
        self.search_query = ""
        self._drag_state: dict[str, object] | None = None
        self._slot_views: dict[str, dict[int, ft.Container]] = {
            HALF_HIGH: {},
            HALF_LOW: {},
        }
        self._scroll_pixels: dict[str, float] = {
            HALF_HIGH: 0.0,
            HALF_LOW: 0.0,
        }
        self._window_first: dict[str, int] = {
            HALF_HIGH: 0,
            HALF_LOW: 0,
        }
        self._slot_stacks: dict[str, ft.Stack] = {}
        self._scroll_lists: dict[str, ft.Column] = {}
        self._resize_token = 0
        self._layout_token = 0
        self._layout_width = 0.0
        self._layout_busy = False
        self._layout_bucket = (
            "compact" if is_compact_layout(page) else "normal"
        )
        self._half_widths: dict[str, float] = {}
        self._dice_container: ft.Container | None = None
        self._divider_container: ft.Container | None = None
        self._last_width = self._button_width()
        register_resize_handler(page, "/watchlist", self._on_resize)
        self.columns_host = ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[],
        )
        self.search_field = ft.TextField(
            hint_text="搜索动画",
            text_size=14,
            border_radius=8,
            on_change=self._on_search_change,
        )
        self.content = ft.Column(
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[self.columns_host, self.search_field],
        )
        self.view = ft.View(
            route="/watchlist",
            appbar=ft.AppBar(
                title=ui_text("已追"),
                automatically_imply_leading=False,
                leading=back_icon(self.page, "/"),
            ),
            padding=page_padding(),
            controls=[
                ft.Column(
                    expand=True,
                    scroll=self._scroll_setting(
                        ft.ScrollbarOrientation.RIGHT
                    ),
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[self.content],
                )
            ],
        )
        self.refresh()

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._reset_drag()
        self.high, self.low = load_watchlist()
        self._render_columns()

    def _render_columns(self, preserve_scroll: bool = False) -> None:
        if not preserve_scroll:
            for half in (HALF_HIGH, HALF_LOW):
                self._scroll_pixels[half] = 0.0
                self._window_first[half] = 0
        self._scroll_lists.clear()
        self.columns_host.controls = [self._build_columns()]

    def _on_resize(self, event=None) -> None:
        # 仅栈顶响应；断点变化必须重建，否则宽度差 ≥8px 才重建。
        if (
            not self.page.views
            or self.page.views[-1] is not self.view
        ):
            return
        bucket = (
            "compact"
            if is_compact_layout(self.page)
            else "normal"
        )
        changed = bucket != self._layout_bucket
        if changed:
            self._layout_bucket = bucket
        target = float(self._button_width())
        if not changed:
            measured = (
                self._half_widths.get(HALF_HIGH)
                or self._half_widths.get(HALF_LOW)
            )
            if measured and abs(target - self._layout_width) < 8.0:
                return
        self.schedule_layout(target)

    def schedule_layout(self, width: float) -> None:
        """统一防抖：0.12s 内只保留最后一次，容差 2px。"""
        if self._layout_busy:
            return
        if abs(width - self._layout_width) < 2.0:
            return
        self._layout_token += 1
        token = self._layout_token
        self.page.run_task(self._apply_layout, token, width)

    async def _apply_layout(self, token: int, width: float) -> None:
        await asyncio.sleep(0.2)
        if token != self._layout_token or self._layout_busy:
            return
        # 执行时按当前宽度重新计算目标。
        width = float(self._button_width())
        if abs(width - self._layout_width) < 2.0:
            return
        self._layout_busy = True
        try:
            self._layout_width = width
            self._last_width = int(width)
            offsets = dict(self._scroll_pixels)
            self._render_columns(preserve_scroll=True)
            # 不逐个 await，减少客户端刷新次数。
            for half, column in self._scroll_lists.items():
                self.page.run_task(
                    column.scroll_to,
                    offsets.get(half, 0.0),
                )
            self.page.update()
            # 留一点时间让测量事件走完，避免重建反馈环。
            await asyncio.sleep(0.12)
        except Exception:
            pass
        finally:
            self._layout_busy = False

    def _on_shown(self) -> None:
        """返回已追页时重算虚拟窗口并恢复滚动位置。"""
        if (
            not self.page.views
            or self.page.views[-1] is not self.view
        ):
            return
        offsets = dict(self._scroll_pixels)
        self._render_columns(preserve_scroll=True)
        try:
            self.columns_host.update()
        except RuntimeError:
            return
        self.page.run_task(self._restore_after_shown, offsets)

    async def _restore_after_shown(
        self,
        offsets: dict[str, float],
    ) -> None:
        await asyncio.sleep(0.05)
        for half, column in self._scroll_lists.items():
            try:
                await column.scroll_to(
                    offset=offsets.get(half, 0.0)
                )
            except Exception:
                pass

    def _on_search_change(self, event: ft.ControlEvent) -> None:
        self._reset_drag()
        self.search_query = (
            (event.control.value or "").strip().casefold()
        )
        self._render_columns()
        self.columns_host.update()

    def _search_active(self) -> bool:
        field = getattr(self, "search_field", None)
        text = getattr(field, "value", "") if field is not None else ""
        return bool(str(text or "").strip())

    def _button_width(self, half: str | None = None) -> int:
        page_width = self.page.width or DEFAULT_PAGE_WIDTH
        max_label = text_width(
            "中" * MAX_LABEL_CHARS,
            size=LABEL_SIZE,
        )
        measured = None
        if half is not None:
            measured = self._half_widths.get(half)
        elif self._half_widths:
            measured = min(self._half_widths.values())
        return button_width(page_width, max_label, measured)

    def _filtered(self, items: list[str]) -> list[str]:
        if not self.search_query:
            return items
        from bangumi.core.pinyin_search import matches

        return [
            name
            for name in items
            if matches(name, self.search_query)
        ]



    def _scroll_setting(
        self,
        orientation: ft.ScrollbarOrientation,
    ) -> ft.Control | ft.ScrollMode:
        if is_compact_layout(self.page):
            return ft.ScrollMode.HIDDEN
        return ft.Scrollbar(
            orientation=orientation,
            thumb_visibility=True,
            track_visibility=True,
        )

    def _list_height(self) -> float:
        return list_height(
            is_compact_layout(self.page)
        )

    def _window_size(self) -> int:
        return window_size(
            self._list_height(),
            BUTTON_HEIGHT + BUTTON_SPACING,
        )

    def _max_scroll_offset(self, count: int) -> float:
        return max_scroll_offset(
            count,
            BUTTON_HEIGHT + BUTTON_SPACING,
            self._list_height(),
            BUTTON_SPACING,
        )

    def _clamp_scroll_pixels(
        self,
        half: str,
        pixels: float,
        count: int,
    ) -> float:
        return clamp_scroll(
            pixels,
            self._max_scroll_offset(count),
        )

    def _window_bounds(
        self,
        half: str,
        count: int,
    ) -> tuple[int, int, int]:
        step = BUTTON_HEIGHT + BUTTON_SPACING
        size = self._window_size()
        pixels = self._clamp_scroll_pixels(
            half,
            float(self._scroll_pixels.get(half, 0.0)),
            count,
        )
        first, last = window_bounds(
            pixels,
            count,
            size,
            step,
            overscan=2,
        )
        return first, last, size

    def _create_slot_view(
        self,
        half: str,
        items: list[str],
        index: int,
        color: str,
        width: int,
        drag_enabled: bool,
    ) -> ft.Container:
        step = BUTTON_HEIGHT + BUTTON_SPACING
        view = ft.Container(
            width=width,
            height=BUTTON_HEIGHT,
            left=0,
            top=index * step,
            scale=ft.Scale(1.0, alignment=ft.Alignment.CENTER),
            animate_scale=animation(
                SCALE_ANIMATION_MS,
                ft.AnimationCurve.EASE_OUT,
            ),
        )
        view.content = self._build_slot(
            half,
            items,
            index,
            color,
            width,
            drag_enabled,
            view,
        )
        return view

    def _on_list_scroll(
        self,
        event: ft.ControlEvent,
        half: str,
    ) -> None:
        ft.context.mark_update_called()
        if self._drag_state is not None:
            return
        raw = getattr(event, "pixels", 0.0)
        try:
            pixels = float(raw)
        except (TypeError, ValueError):
            return
        if not math.isfinite(pixels):
            return
        items = self._filtered(self._items(half))
        count = len(items)
        min_extent = getattr(event, "min_scroll_extent", None)
        max_extent = getattr(event, "max_scroll_extent", None)
        if (
            isinstance(min_extent, (int, float))
            and math.isfinite(min_extent)
        ):
            pixels = max(pixels, float(min_extent))
        if (
            isinstance(max_extent, (int, float))
            and math.isfinite(max_extent)
        ):
            pixels = min(pixels, float(max_extent))
        pixels = self._clamp_scroll_pixels(half, pixels, count)
        self._scroll_pixels[half] = pixels
        first, last, _ = self._window_bounds(half, count)
        if count == 0 or last < first:
            return
        if first == self._window_first.get(half, 0):
            return
        stack = self._slot_stacks.get(half)
        if stack is None:
            return
        color = HIGH_COLOR if half == HALF_HIGH else LOW_COLOR
        width = self._button_width()
        drag_enabled = not self._search_active()
        existing = self._slot_views.get(half, {})
        slot_views: dict[int, ft.Container] = {}
        for index in range(first, last + 1):
            view = existing.get(index)
            if view is None:
                view = self._create_slot_view(
                    half,
                    items,
                    index,
                    color,
                    width,
                    drag_enabled,
                )
            slot_views[index] = view
        self._slot_views[half] = slot_views
        self._window_first[half] = first
        stack.controls = list(slot_views.values())
        stack.update()

    def _build_columns(self) -> ft.Column:
        foreground = foreground_color(self.page)
        drag_enabled = not self._search_active()
        page_width = float(self.page.width or 1000)
        gap = divider_gap(page_width)
        android = is_compact_layout(self.page)
        list_height = self._list_height()
        divider_color = ft.Colors.with_opacity(0.35, foreground)
        # 标题行 + 列表行共用一条竖线，骰子放到下面的按钮行。
        title_row = ft.Row(
            spacing=gap,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self._half_title(HALF_HIGH, foreground),
                ft.Container(
                    width=DIVIDER_WIDTH,
                    height=TITLE_HEIGHT,
                    bgcolor=divider_color,
                ),
                self._half_title(HALF_LOW, foreground),
            ],
        )
        list_row = ft.Row(
            spacing=gap,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                self._build_half_list(
                    HALF_HIGH,
                    self._filtered(self.high),
                    HIGH_COLOR,
                    drag_enabled=drag_enabled,
                ),
                ft.Container(
                    width=DIVIDER_WIDTH,
                    height=list_height,
                    bgcolor=divider_color,
                ),
                self._build_half_list(
                    HALF_LOW,
                    self._filtered(self.low),
                    LOW_COLOR,
                    drag_enabled=drag_enabled,
                ),
            ],
        )
        button_row = ft.Row(
            spacing=gap,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER,
                    content=self._half_buttons(HALF_HIGH, android),
                ),
                ft.Container(
                    width=self._dice_px(),
                    content=ft.Column(
                        spacing=4,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),
                        controls=[
                            self._build_dice_button(),
                            self._build_bilibili_image(),
                        ],
                    ),
                ),
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER,
                    content=self._half_buttons(HALF_LOW, android),
                ),
            ],
        )
        return ft.Column(
            spacing=0,
            controls=[
                title_row,
                list_row,
                ft.Container(height=8),
                button_row,
            ],
        )

    def _usable_width(self) -> float:
        """优先用左右半列实测宽度推算可用宽度。"""
        gap = divider_gap(float(self.page.width or 1000))
        measured = [
            value
            for value in self._half_widths.values()
            if value and value > 0
        ]
        if measured:
            return max(
                1.0,
                sum(measured[:2])
                + DIVIDER_WIDTH
                + gap * 2,
            )
        page_width = float(self.page.width or 1000)
        return max(
            1.0,
            page_width - PAGE_HORIZONTAL_PADDING * 2,
        )

    def _dice_px(self, usable: float | None = None) -> float:
        """可用宽度 < 420 时骰子缩到 36px，避免遮挡按钮。"""
        if usable is None:
            usable = self._usable_width()
        return 36.0 if usable < 420.0 else float(DICE_SIZE)

    def _divider_height(self, dice_px: float) -> float:
        """竖线止于骰子块上方，避免穿模。"""
        block = dice_px + 4.0 + dice_px
        return max(0.0, HALF_HEIGHT - block - 8.0)

    def _sync_middle(self) -> None:
        """按实测宽度更新骰子位置与竖线高度。"""
        if (
            self._dice_container is None
            or self._divider_container is None
        ):
            return
        usable = self._usable_width()
        dice_px = self._dice_px(usable)
        self._dice_container.width = dice_px
        self._dice_container.left = max(
            0.0, (usable - dice_px) / 2
        )
        self._divider_container.height = self._divider_height(
            dice_px
        )
        for control in (
            self._dice_container,
            self._divider_container,
        ):
            try:
                control.update()
            except Exception:
                pass

    def _on_half_size(
        self,
        half: str,
        event: ft.ControlEvent,
    ) -> None:
        """只记录实测宽度并调度；不在回调里直接重建。"""
        width = float(getattr(event, "width", 0) or 0)
        if width <= 0:
            return
        self._half_widths[half] = width
        if self._layout_busy:
            return
        self.schedule_layout(float(self._button_width(half)))

    def _half_title(self, half: str, foreground: str) -> ft.Container:
        return ft.Container(
            expand=1,
            height=TITLE_HEIGHT,
            alignment=ft.Alignment.CENTER,
            content=ui_text(
                "高优先级" if half == HALF_HIGH else "低优先级",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=foreground,
            ),
        )

    def _half_buttons(self, half: str, android: bool) -> ft.Container:
        return ft.Container(
            height=(
                ANDROID_BUTTON_AREA_HEIGHT
                if android
                else BUTTON_ROW_HEIGHT
            ),
            content=self._build_button_row(
                half,
                self._items(half),
            ),
        )

    def _build_half_list(
        self,
        half: str,
        items: list[str],
        color: str,
        *,
        drag_enabled: bool,
    ) -> ft.Container:
        width = self._button_width(half)
        # 记录本次渲染实际使用的宽度，供下次比对。
        self._half_widths[half] = float(width)
        step = BUTTON_HEIGHT + BUTTON_SPACING
        count = len(items)
        list_height = self._list_height()
        content_height = max(
            list_height,
            count * step - BUTTON_SPACING,
        )
        first, last, _ = self._window_bounds(half, count)
        slot_views: dict[int, ft.Container] = {}
        for index in range(first, last + 1):
            slot_views[index] = self._create_slot_view(
                half,
                items,
                index,
                color,
                width,
                drag_enabled,
            )
        self._slot_views[half] = slot_views
        self._window_first[half] = first
        stack = ft.Stack(
            width=width,
            height=content_height,
            controls=list(slot_views.values()),
        )
        self._slot_stacks[half] = stack
        column = ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.HIDDEN,
            on_scroll=(
                lambda event, h=half: self._on_list_scroll(
                    event,
                    h,
                )
            ),
            controls=[stack],
        )
        self._scroll_lists[half] = column
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.TOP_CENTER,
            on_size_change=(
                lambda event, h=half: self._on_half_size(h, event)
            ),
            content=ft.Container(
                height=list_height,
                content=column,
            ),
        )

    def _build_button_row(
        self,
        half: str,
        items: list[str],
    ) -> ft.Control:
        add_button = ft.Button(
            content=ui_text("追加"),
            height=BUTTON_ROW_HEIGHT,
            on_click=lambda event, h=half: self._open_add(h),
        )
        random_button = ft.Button(
            content=ui_text("随机"),
            height=BUTTON_ROW_HEIGHT,
            disabled=not items,
            on_click=lambda event, h=half: self._random(h),
        )
        clear_button = ft.Button(
            content=ui_text("清空"),
            height=BUTTON_ROW_HEIGHT,
            disabled=not items,
            on_click=lambda event, h=half: self._request_clear(h),
        )
        controls = (
            [add_button, random_button, clear_button]
            if half == HALF_HIGH
            else [clear_button, random_button, add_button]
        )
        if is_compact_layout(self.page):
            return ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=BUTTON_SPACING,
                controls=[add_button, random_button, clear_button],
            )
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            controls=controls,
        )

    def _build_slot(
        self,
        half: str,
        items: list[str],
        index: int,
        color: str,
        width: int,
        drag_enabled: bool,
        view: ft.Container,
    ) -> ft.Control:
        name = items[index] if index < len(items) else None
        if name is None:
            return ft.Container(
                width=width,
                height=BUTTON_HEIGHT,
            )
        label = self.fit_label(name, width)
        button = ft.Container(
            width=width,
            height=BUTTON_HEIGHT,
            bgcolor=color,
            border_radius=8,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(
                horizontal=BUTTON_PADDING,
            ),
            scale=ft.Scale(1.0),
            animate_scale=animation(
                SCALE_ANIMATION_MS,
                ft.AnimationCurve.EASE_OUT,
            ),
            content=ui_text(
                label,
                size=LABEL_SIZE,
                color=BUTTON_TEXT_COLOR,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.CENTER,
            ),
        )

        def on_hover(
            event: ft.ControlEvent,
            control: ft.Container = button,
        ) -> None:
            if self._drag_state is not None:
                return
            hovered = is_hover(event)
            control.scale = ft.Scale(HOVER_SCALE if hovered else 1.0)
            control.update()

        button.on_hover = on_hover
        gesture = ft.GestureDetector(
            content=button,
            # 单击打开详情；拖拽进行中不响应。
            on_tap=(
                lambda event, n=name, h=half: (
                    self._open_detail(n, h)
                    if self._drag_state is None
                    else None
                )
            ),
        )
        if not drag_enabled:
            return gesture
        gesture.on_long_press_start = (
            lambda event, i=index: self._start_drag(
                event,
                view,
                half,
                i,
            )
        )
        gesture.on_long_press_move_update = self._move_drag
        gesture.on_long_press_end = self._finish_drag
        gesture.on_long_press_cancel = lambda event: self._reset_drag()
        return gesture

    def _start_drag(
        self,
        event: ft.ControlEvent,
        view: ft.Container,
        half: str,
        index: int,
    ) -> None:
        ft.context.mark_update_called()
        if self._search_active():
            return
        self._reset_drag()
        _, y = event_position(event)
        step = BUTTON_HEIGHT + BUTTON_SPACING
        count = len(self._items(half))
        content_height = max(
            self._list_height(),
            count * step - BUTTON_SPACING,
        )
        self._drag_state = {
            "half": half,
            "index": index,
            "view": view,
            "origin_y": y,
            "start_top": index * step,
            "last_top": index * step,
            "last_move": 0.0,
            "content_height": content_height,
            "count": count,
            "target": index,
        }
        view.scale = ft.Scale(DRAG_SCALE, alignment=ft.Alignment.CENTER)
        view.update()

    def _move_drag(self, event: ft.ControlEvent) -> None:
        state = self._drag_state
        ft.context.mark_update_called()
        if self._search_active():
            self._reset_drag()
            return
        if state is None:
            return
        step = BUTTON_HEIGHT + BUTTON_SPACING
        _, y = event_position(event)
        drag_top = float(state["start_top"]) + (
            y - float(state["origin_y"])
        )
        drag_top = max(
            0.0,
            min(
                float(state["content_height"]) - BUTTON_HEIGHT,
                drag_top,
            ),
        )
        count = int(state["count"])
        target = round(drag_top / step)
        target = max(0, min(count - 1, target))
        changed_target = target != int(state["target"])
        now = time.monotonic()
        if (
            not changed_target
            and now - float(state["last_move"]) < DRAG_FRAME_INTERVAL
        ):
            return
        state["last_move"] = now
        view = state["view"]
        if abs(drag_top - float(state["last_top"])) >= 0.5:
            view.top = drag_top
            state["last_top"] = drag_top
            view.update()
        if not changed_target:
            return
        state["target"] = target
        source = int(state["index"])
        for index, slot in self._slot_views.get(
            str(state["half"]), {}
        ).items():
            if index == source:
                continue
            slot_top = index * step
            if source < target and source < index <= target:
                slot_top -= step
            elif target < source and target <= index < source:
                slot_top += step
            if slot.top != slot_top:
                slot.top = slot_top
                slot.update()

    def _finish_drag(self, event: ft.ControlEvent) -> None:
        state = self._drag_state
        if state is None:
            return
        if self._search_active():
            self._reset_drag()
            return
        self._drag_state = None
        half = str(state["half"])
        source = int(state["index"])
        step = BUTTON_HEIGHT + BUTTON_SPACING
        view = state["view"]
        items = self._items(half)
        target = int(state["target"])
        if items:
            target = max(0, min(len(items) - 1, target))
        else:
            target = source
        view.top = source * step
        view.scale = ft.Scale(1.0, alignment=ft.Alignment.CENTER)
        view.update()
        if target != source and items:
            item = items.pop(source)
            items.insert(target, item)
            save_watchlist(self.high, self.low)
            self._refresh_slots(half)

    def _refresh_slots(self, half: str) -> None:
        ft.context.mark_update_called()
        items = self._items(half)
        step = BUTTON_HEIGHT + BUTTON_SPACING
        color = HIGH_COLOR if half == HALF_HIGH else LOW_COLOR
        width = self._button_width()
        drag_enabled = not self._search_active()
        for index, view in self._slot_views.get(half, {}).items():
            if index >= len(items):
                continue
            view.top = index * step
            view.scale = ft.Scale(1.0, alignment=ft.Alignment.CENTER)
            view.content = self._build_slot(
                half,
                items,
                index,
                color,
                width,
                drag_enabled,
                view,
            )
            view.update()

    def _reset_drag(self) -> None:
        ft.context.mark_update_called()
        state = self._drag_state
        if state is None:
            return
        self._drag_state = None
        half = str(state["half"])
        source = int(state["index"])
        step = BUTTON_HEIGHT + BUTTON_SPACING
        view = state["view"]
        view.top = source * step
        view.scale = ft.Scale(1.0, alignment=ft.Alignment.CENTER)
        updates = [view]
        for index, slot in self._slot_views.get(half, {}).items():
            if index == source:
                continue
            base = index * step
            if slot.top != base:
                slot.top = base
                updates.append(slot)
        for control in updates:
            control.update()

    def fit_label(self, name: str, width: int) -> str:
        return fit_label(name, width)

    def _build_dice_button(self) -> ft.Control:
        dice_px = self._dice_px()
        icon_size = 24 if dice_px < 48 else 32
        return hover_icon(
            self.page,
            ft.Icons.CASINO,
            size=icon_size,
            padding=max(0, int((dice_px - icon_size) / 2)),
            disabled=not (self.high or self.low),
            on_click=lambda event: self._roll_dice(),
        )

    def _build_bilibili_image(self) -> ft.Control:
        bilibili_px = self._dice_px()
        return ft.Container(
            width=bilibili_px,
            height=bilibili_px,
            alignment=ft.Alignment.CENTER,
            on_click=self._open_bilibili_import,
            content=hover_zoom(
                self.page,
                ft.Image(
                    src="/pic/bilibili.png",
                    width=bilibili_px,
                    height=bilibili_px,
                    fit=ft.BoxFit.CONTAIN,
                ),
                scale=1.2
            ),
        )

    def _open_bilibili_import(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        open_bilibili_import(
            self.page,
            self._import_bilibili_async,
        )

    async def _import_bilibili_async(
        self,
        uid: str,
        half: str,
    ) -> None:
        try:
            titles = await asyncio.to_thread(
                fetch_bilibili_following,
                uid,
                # 1=想看，2=在看
                {1, 2},
            )
        except BilibiliImportError as error:
            self._show_import_result("导入失败", str(error))
            return
        except requests.RequestException:
            self._show_import_result("导入失败", "网络连接失败")
            return
        except Exception as error:
            self._show_import_result(
                "导入失败",
                f"导入失败：{error}",
            )
            return

        if not titles:
            self._show_import_result(
                "导入失败",
                "该用户没有想看/在看的追番",
            )
            return

        high, low = load_watchlist()
        items = high if half == "high" else low
        before = len(items)
        for title in titles:
            if title not in items:
                items.append(title)
        save_watchlist(high, low)
        save_bilibili_uid(uid)
        saved_high, saved_low = load_watchlist()
        after = len(saved_high if half == "high" else saved_low)
        added = max(0, after - before)
        try:
            self.refresh()
            self.columns_host.update()
        except Exception:
            pass
        label = "高优先级" if half == "high" else "低优先级"
        self._show_import_result(
            "导入完成",
            f"导入完成：已向{label}新增 {added} 条追番",
        )

    def _show_import_result(
        self,
        title: str,
        message: str,
    ) -> None:
        show_import_result(self.page, title, message)

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------

    def _items(self, half: str) -> list[str]:
        return self.high if half == HALF_HIGH else self.low

    def _request_clear(self, half: str) -> None:
        message = (
            "你确定清除高优先级的列表吗？"
            if half == HALF_HIGH
            else "你确定清除低优先级的列表吗？"
        )
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="清空列表",
                message=message,
                confirm_label="清空",
                on_confirm=lambda event: self._clear_half(half),
            )
        )

    def _clear_half(self, half: str) -> None:
        self.page.pop_dialog()
        self._items(half).clear()
        save_watchlist(self.high, self.low)
        self.refresh()
        self.columns_host.update()

    def _random(self, half: str) -> None:
        items = self._items(half)
        if not items:
            return
        self._open_detail(random.choice(items), half)

    def _roll_dice(self) -> None:
        options = [
            (name, HALF_HIGH) for name in self.high
        ] + [
            (name, HALF_LOW) for name in self.low
        ]
        if not options:
            return
        name, half = random.choice(options)
        self._open_detail(name, half)

    def _open_detail(self, name: str, half: str) -> None:
        route = f"/watchlist/detail/{quote(name, safe='')}"
        view = build_watchlist_detail_view(
            self.page,
            name,
            on_finish=lambda: self._finish(name, half, view),
            on_drop=lambda: self._drop(name, half, view),
            route=route,
        )
        push_view(self.page, view)

    def _open_add(self, half: str) -> None:
        title = (
            "追番 —— 高优先级"
            if half == HALF_HIGH
            else "追番 —— 低优先级"
        )
        view = build_append_from_text_view(
            self.page,
            title,
            on_confirm=lambda text: self._save_added(half, text, view),
            on_cancel=lambda: self._close_add(view),
            route=f"/watchlist/add/{half}",
        )
        push_view(self.page, view)

    def _save_added(
        self,
        half: str,
        text: str,
        view: ft.View,
    ) -> None:
        names = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]
        if half == HALF_HIGH:
            target, other = self.high, self.low
        else:
            target, other = self.low, self.high
        for name in names:
            if name in target:
                continue
            if name in other:
                other.remove(name)
            target.append(name)
        save_watchlist(self.high, self.low)
        go_back(self.page, str(getattr(view, "route", "") or ""))
        self.refresh()
        self.columns_host.update()

    def _close_add(self, view: ft.View) -> None:
        go_back(self.page, str(getattr(view, "route", "") or ""))

    def _finish(self, name: str, half: str, view: ft.View) -> None:
        open_entry_form(
            self.page,
            record={"entry": name, "anime": name},
            on_save=lambda record: self._save_finished(
                record,
                name,
                half,
                view,
            ),
        )

    def _save_finished(
        self,
        record: Record,
        name: str,
        half: str,
        view: ft.View,
    ) -> None:
        records = load_records()
        updated = [*records, record]
        if record.get("sequel") is True:
            propagate_sequel(
                updated,
                entry_group_key(record),
                True,
            )
        save_records(updated)
        sync_tag_colors(updated, Preferences.load())
        self._remove(name, half)
        go_back(self.page, str(getattr(view, "route", "") or ""))
        self.refresh()

    def _drop(self, name: str, half: str, view: ft.View) -> None:
        self._remove(name, half)
        go_back(self.page, str(getattr(view, "route", "") or ""))
        self.refresh()
        self.columns_host.update()
        show_toast(
            self.page,
            "不知是错过了一部良作，还是少吃了一坨史",
        )

    def _remove(self, name: str, half: str) -> None:
        items = self._items(half)
        if name in items:
            items.remove(name)
        save_watchlist(self.high, self.low)


def open_bilibili_import(page: ft.Page, on_import) -> None:
    """弹出 Bilibili 追番导入对话框（UID 与优先级）。"""
    foreground = foreground_color(page)
    uid_field = ft.TextField(
        width=180,
        height=40,
        value=load_bilibili_uid(),
        hint_text="请输入UID",
        input_filter=ft.NumbersOnlyInputFilter(),
        text_size=14,
        border_radius=8,
        content_padding=ft.Padding.symmetric(
            horizontal=10,
            vertical=8,
        ),
    )
    error_text = ui_text(
        "",
        size=12,
        color=ft.Colors.RED,
        visible=False,
    )
    target = {"high": False}
    toggle = ft.Button(content=ui_text("低优先级"))

    def toggle_target(event: ft.ControlEvent) -> None:
        target["high"] = not target["high"]
        toggle.content = ui_text(
            "高优先级" if target["high"] else "低优先级"
        )
        toggle.update()

    toggle.on_click = toggle_target

    def confirm(event: ft.ControlEvent) -> None:
        uid = (uid_field.value or "").strip()
        if not uid:
            error_text.value = "请输入UID"
            error_text.visible = True
            error_text.update()
            return
        half = "high" if target["high"] else "low"
        page.pop_dialog()
        page.run_task(on_import, uid, half)

    def cancel(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text(
                "导入 Bilibili 追番",
                weight=ft.FontWeight.BOLD,
                color=foreground,
            ),
            title_text_style=ui_text_style(
                color=foreground,
                weight=ft.FontWeight.BOLD,
            ),
            content_text_style=ui_text_style(color=foreground),
            content=ft.Container(
                width=min(
                    360.0,
                    max(240.0, float(page.width or 400) * 0.82),
                ),
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Row(
                            [
                                ui_text(
                                    "UID",
                                    weight=ft.FontWeight.BOLD,
                                ),
                                uid_field,
                            ],
                            spacing=12,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                        ),
                        error_text,
                        ft.Row(
                            [
                                ui_text(
                                    "导入至",
                                    weight=ft.FontWeight.BOLD,
                                ),
                                toggle,
                            ],
                            spacing=12,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.Button(
                    content=ui_text("取消"),
                    on_click=cancel,
                ),
                ft.Button(
                    content=ui_text(
                        "确认",
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.BLUE,
                    on_click=confirm,
                ),
            ],
        )
    )


def show_import_result(
    page: ft.Page,
    title: str,
    message: str,
) -> None:
    """显示导入结果弹窗。"""
    foreground = foreground_color(page)

    def close(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text(
                title,
                weight=ft.FontWeight.BOLD,
                color=foreground,
            ),
            title_text_style=ui_text_style(
                color=foreground,
                weight=ft.FontWeight.BOLD,
            ),
            content=ui_text(message, color=foreground),
            content_text_style=ui_text_style(color=foreground),
            actions=[
                ft.Button(
                    content=ui_text("关闭"),
                    on_click=close,
                ),
            ],
        )
    )


def watchlist_view(page: ft.Page) -> ft.View:
    instance = WatchlistPage(page)
    # 合并写入，保留可能的其它字段。
    data = (
        instance.view.data
        if isinstance(instance.view.data, dict)
        else {}
    )
    data["rebuild"] = lambda: watchlist_view(page)
    data["on_shown"] = instance._on_shown
    instance.view.data = data
    return instance.view
