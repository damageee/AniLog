"""已阅页面 mixin：search。"""

from __future__ import annotations


import asyncio

import flet as ft

from bangumi.ui.text_metrics import text_width, truncate_display
from bangumi.ui.theme import (
    ui_text_style,
)
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.ui.interaction import (
    hover_icon,
)
from bangumi.views.general.detail_role import first_role_name
from bangumi.data.watched_data import (
    Record,
    staff_display,
    split_tags,
)

from bangumi.views.watched.constants import *


def display_broadcast(record: Record) -> str:
    """界面上显示的放送文本；搜索与高亮都以它为准。"""
    return str(record.get("broadcast", "") or "").replace("\n", " ")


class SearchMixin:

    def _create_search_field(self) -> ft.TextField:
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        foreground = foreground_color(self.page)
        secondary = (
            ft.Colors.GREY_400 if dark else ft.Colors.GREY_600
        )
        return ft.TextField(
            height=40,
            text_size=14,
            text_style=ui_text_style(
                size=14,
                color=foreground,
            ),
            hint_text="搜索动画、制作公司…",
            hint_style=ui_text_style(
                size=14,
                color=secondary,
            ),
            bgcolor=background_color(self.page),
            border=ft.OutlineInputBorder(border_radius=8),
            border_radius=8,
            border_color=(
                ft.Colors.GREY_600 if dark else ft.Colors.GREY_400
            ),
            focused_border_color=ft.Colors.BLUE,
            content_padding=ft.Padding.only(
                left=12,
                right=36,
                top=10,
                bottom=10,
            ),
            on_submit=self._on_search_submit,
            on_change=self._on_search_change,
            on_focus=self._on_search_focus,
            on_blur=self._on_search_blur,
        )

    def _on_search_change(self, event: ft.ControlEvent) -> None:
        """输入防抖 120ms，停手后再过滤。"""
        value = str(event.control.value or "")
        self._search_token += 1
        token = self._search_token
        self.page.run_task(self._debounced_search, token, value)

    async def _debounced_search(self, token: int, value: str) -> None:
        await asyncio.sleep(0.12)
        if token != self._search_token:
            return
        # 只有与上次实际应用的查询不同才重算（初始为空也允许跑一次）。
        if value == getattr(self, "_applied_query", None):
            return
        self._applied_query = value
        self.search_query = value
        self._refresh_search(reset_current=True)

    def _create_search_box(self) -> ft.Stack:
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        return ft.Stack(
            expand=True,
            height=40,
            controls=[
                ft.Container(
                    left=0,
                    right=0,
                    top=0,
                    bottom=0,
                    content=self.search_field,
                    expand=True,
                ),
                ft.Container(
                    right=12,
                    top=0,
                    bottom=0,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(
                        ft.Icons.SEARCH,
                        size=18,
                        color=(
                            ft.Colors.GREY_400
                            if dark
                            else ft.Colors.GREY_500
                        ),
                    ),
                ),
            ],
        )

    def _create_search_buttons(
        self,
    ) -> tuple[ft.Container, ft.Container]:
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        icon_color = ft.Colors.GREY_300 if dark else ft.Colors.GREY_700
        prev_button = hover_icon(
            self.page,
            ft.Icons.KEYBOARD_ARROW_UP,
            size=20,
            color=icon_color,
            tooltip="上一个结果",
            on_click=lambda event: self._step_search(-1),
            padding=6,
        )
        prev_button.disabled = True
        next_button = hover_icon(
            self.page,
            ft.Icons.KEYBOARD_ARROW_DOWN,
            size=20,
            color=icon_color,
            tooltip="下一个结果",
            on_click=lambda event: self._step_search(1),
            padding=6,
        )
        next_button.disabled = True
        return prev_button, next_button

    def _create_search_row(self) -> ft.Row:
        return ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.search_box,
                self.search_count,
                self.search_next_button,
                self.search_prev_button,
            ],
        )

    def _search_text(self, record: Record, key: str) -> str:
        if key == "broadcast":
            return display_broadcast(record)
        if key == "staff":
            return staff_display(record)
        if key == "role":
            return first_role_name(
                str(record.get("role", "") or "")
            )
        if key == "remark":
            return truncate_display(
                str(record.get("remark", "") or ""),
                100,
            )
        return str(record.get(key, "") or "").replace("\n", " ")

    def _tag_at_offset(
        self,
        record: Record,
        offset: int,
    ) -> str | None:
        raw = str(record.get("tag", "") or "")
        position = 0
        for tag in split_tags(raw):
            index = raw.find(tag, position)
            if index == -1:
                continue
            if index <= offset < index + len(tag):
                return tag
            position = index + len(tag)
        return None

    def _search_columns(self) -> list[str]:
        # 只搜索当前可见列；制作公司在窄布局下隐藏。
        columns = ["anime", "staff", "tag", "broadcast"]
        if float(self.page.width or 1000) >= 1100:
            columns.insert(3, "studio")
        return columns

    def _recompute_search(self) -> None:
        if not self.search_query:
            self.search_results = []
            return
        from bangumi.core.pinyin_search import find_spans

        results: list[tuple[int, str, int, int, int]] = []
        columns = self._search_columns()
        for record_index, record in enumerate(self._display_records()):
            for key in columns:
                text = self._search_text(record, key)
                for occurrence, (start, end) in enumerate(
                    find_spans(text, self.search_query)
                ):
                    results.append(
                        (
                            record_index,
                            key,
                            start,
                            end,
                            occurrence,
                        )
                    )
        self.search_results = results

    def _fit_search_count(self) -> None:
        text = self.search_count.value or ""
        base = 13
        avail = max(20, (self.search_count.width or 90) - 8)
        w = text_width(text, size=base)
        size = (
            base
            if w <= avail
            else max(8, int(base * avail / max(1, w)))
        )
        self.search_count.size = size

    def _update_search_buttons(self) -> None:
        enabled = bool(self.search_results)
        self.search_prev_button.disabled = not enabled
        self.search_next_button.disabled = not enabled
        self.search_count.value = (
            f"{len(self.search_results)}条结果"
            if self.search_query
            else ""
        )
        self._fit_search_count()
        # 立即下发按钮与计数，避免只更新表体后头部不刷新。
        for control in (
            self.search_prev_button,
            self.search_next_button,
            self.search_count,
        ):
            try:
                control.update()
            except Exception:
                pass

    async def _refocus_search(self) -> None:
        """延迟重聚焦，避免被客户端 submit 行为抢走焦点。"""
        await asyncio.sleep(0.05)
        try:
            self.search_field.focus()
            self.page.update()
        except Exception:
            pass

    def _on_search_focus(self, event: ft.ControlEvent) -> None:
        self._search_focused = True

    def _on_search_blur(self, event: ft.ControlEvent) -> None:
        self._search_focused = False

    def _on_search_submit(self, event: ft.ControlEvent) -> None:
        # 回车只做一件事：定位第一条（随后自然失焦）。
        value = str(event.control.value or "")
        self._search_token += 1
        self.search_query = value
        self._applied_query = value
        self.search_field.value = value
        self._refresh_search(reset_current=True)

    def _step_search(self, delta: int) -> None:
        if not self.search_results:
            return
        if 0 <= self.search_current < len(self.search_results):
            self.search_current = (
                self.search_current + delta
            ) % len(self.search_results)
        else:
            self.search_current = (
                0 if delta >= 0 else len(self.search_results) - 1
            )
        self._show_search_result()

    def _refresh_search(self, *, reset_current: bool = False) -> None:
        self._recompute_search()
        if not self.search_results:
            self._search_token += 1
            self.search_current = -1
            self._update_search_buttons()
            self.refresh(update_header=False)
            return
        if reset_current or self.search_current < 0:
            self.search_current = 0
        else:
            self.search_current = min(
                self.search_current,
                len(self.search_results) - 1,
            )
        self._show_search_result()

    def _show_search_result(
        self,
        *,
        update_header: bool = False,
    ) -> None:
        self._update_search_buttons()
        if not self.search_results:
            self.refresh(update_header=update_header)
            return
        self.search_current = min(
            max(self.search_current, 0),
            len(self.search_results) - 1,
        )
        record_index, column_key, _, _, _ = self.search_results[
            self.search_current
        ]
        previous_page = self.current_page
        self.current_page = min(
            max(record_index // self.page_size, 0),
            self._total_pages() - 1,
        )
        self.state.current_page = self.current_page
        if (
            self.current_page == previous_page
            and self.table_exists
            and hasattr(self, "_update_search_rows")
        ):
            # 同页切换：只重绘新旧两行。
            self._update_search_rows(record_index)
            self._update_search_buttons()
            self._schedule_search_scroll(record_index, column_key)
            return
        # 跨页或特殊布局：全量刷新。
        self.refresh(restore_scroll=False)
        self._schedule_search_scroll(record_index, column_key)

    def _schedule_search_scroll(
        self,
        record_index: int,
        column_key: str,
    ) -> None:
        self._search_token += 1
        self.page.run_task(
            self._scroll_to_search_result,
            self._search_token,
            record_index,
            column_key,
        )

    def _resync_search(
        self,
        *,
        reset_scroll: bool = False,
        update_header: bool = False,
    ) -> None:
        if not self.search_query:
            self._search_token += 1
            self.search_results = []
            self.search_current = -1
            self._update_search_buttons()
            self.refresh(
                reset_scroll=reset_scroll,
                update_header=update_header,
            )
            return
        self._recompute_search()
        if not self.search_results:
            self._search_token += 1
            self.search_current = -1
            self._update_search_buttons()
            self.refresh(
                reset_scroll=reset_scroll,
                update_header=update_header,
            )
            return
        self.search_current = min(
            max(self.search_current, 0),
            len(self.search_results) - 1,
        )
        self._show_search_result(update_header=update_header)

    def _clear_search(self) -> None:
        self._search_token += 1
        self.search_query = ""
        self.search_results = []
        self.search_current = -1
        try:
            self.search_field.value = ""
        except Exception:
            pass
        self._update_search_buttons()

