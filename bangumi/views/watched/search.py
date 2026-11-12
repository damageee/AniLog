"""已阅页面 mixin：search。"""

from __future__ import annotations


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
    split_tags,
)

from bangumi.views.watched.constants import *

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
            hint_text="查找",
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
        )

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
        return [
            key
            for key, _ in self._visible_column_labels()
            if key not in ("number", "entry")
        ]

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

    def _on_search_submit(self, event: ft.ControlEvent) -> None:
        self.search_query = str(event.control.value or "")
        self.search_field.value = self.search_query
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
        self.current_page = min(
            max(record_index // self.page_size, 0),
            self._total_pages() - 1,
        )
        self.state.current_page = self.current_page
        self.refresh(
            restore_scroll=False,
            update_header=update_header,
        )
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

