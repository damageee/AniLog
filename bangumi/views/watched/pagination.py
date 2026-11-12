"""已阅页面 mixin：pagination。"""

from __future__ import annotations


import flet as ft

from bangumi.data.preferences import MAX_PAGE_SIZE
from bangumi.ui.platform import is_compact_layout, is_wide
from bangumi.ui.theme import (
    ui_text,
)

from bangumi.views.watched.constants import *

class PaginationMixin:
    def _total_pages(self) -> int:
        return max(
            1,
            (
                len(self._filtered_records())
                + self.page_size
                - 1
            )
            // self.page_size,
        )

    def _pagination_row(self) -> ft.Control:
        total_pages = self._total_pages()
        first_button = ft.Button(
            content=ui_text("首页", size=14),
            disabled=self.current_page <= 0,
            on_click=lambda event: self._set_current_page(0),
        )
        prev_five_button = ft.Button(
            content=ui_text("上五页", size=14),
            disabled=self.current_page < PAGE_STEP,
            on_click=lambda event: self._change_page(-PAGE_STEP),
        )
        prev_button = ft.Button(
            content=ui_text("上一页", size=14),
            disabled=self.current_page <= 0,
            on_click=lambda event: self._change_page(-1),
        )
        next_button = ft.Button(
            content=ui_text("下一页", size=14),
            disabled=self.current_page + 1 >= total_pages,
            on_click=lambda event: self._change_page(1),
        )
        next_five_button = ft.Button(
            content=ui_text("下五页", size=14),
            disabled=self.current_page + PAGE_STEP >= total_pages,
            on_click=lambda event: self._change_page(PAGE_STEP),
        )
        last_button = ft.Button(
            content=ui_text("尾页", size=14),
            disabled=self.current_page + 1 >= total_pages,
            on_click=lambda event: self._set_current_page(
                total_pages - 1
            ),
        )
        if is_compact_layout(self.page):
            return ft.Column(
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[prev_button, next_button],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ui_text("第", size=14),
                            self.page_number_input,
                            ui_text(
                                f"/ {total_pages} 页",
                                size=14,
                            ),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[prev_five_button, next_five_button],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[first_button, last_button],
                    ),
                ],
            )
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                first_button,
                prev_five_button,
                prev_button,
                ui_text("第", size=14),
                self.page_number_input,
                ui_text(f"/ {total_pages} 页", size=14),
                next_button,
                next_five_button,
                last_button,
            ],
        )

    def _create_page_number_input(self) -> ft.TextField:
        return ft.TextField(
            value="1",
            width=54,
            height=36,
            text_size=14,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(
                horizontal=4,
                vertical=0,
            ),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            on_change=self._go_to_page,
        )

    def _go_to_page(self, event: ft.ControlEvent) -> None:
        try:
            requested_page = int(event.control.value)
        except (TypeError, ValueError):
            return
        if requested_page < 1:
            return
        self._set_current_page(requested_page - 1)

    def _change_page(self, offset: int) -> None:
        self._set_current_page(self.current_page + offset)

    def _set_current_page(self, page_index: int) -> None:
        self.current_page = min(
            max(page_index, 0),
            self._total_pages() - 1,
        )
        self.refresh(reset_scroll=True, preserve_vertical=True)

    def _page_size_row(self) -> ft.Row:
        row = getattr(self, "_page_size_row_control", None)
        if row is not None:
            return row
        row = ft.Row(
            alignment=(
                ft.MainAxisAlignment.CENTER
                if is_compact_layout(self.page)
                else ft.MainAxisAlignment.START
            ),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=is_wide(self.page),
            spacing=6,
            controls=[
                ui_text("每页显示"),
                self.page_size_input,
                ui_text("条"),
            ],
        )
        self._page_size_row_control = row
        return row

    def _create_page_size_input(self) -> ft.TextField:
        return ft.TextField(
            value=str(self.page_size),
            width=48,
            height=30,
            text_size=13,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(
                horizontal=4,
                vertical=0,
            ),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            on_blur=self._set_page_size,
        )

    def _set_page_size(self, event: ft.ControlEvent) -> None:
        try:
            updated_page_size = int(event.control.value)
        except (TypeError, ValueError):
            return
        if updated_page_size < 1:
            event.control.error_text = "请输入大于 0 的整数"
            event.control.update()
            return

        updated_page_size = min(updated_page_size, MAX_PAGE_SIZE)
        if updated_page_size == self.page_size:
            event.control.value = str(self.page_size)
            return
        event.control.value = str(updated_page_size)
        event.control.error_text = None

        first_visible_index = self.current_page * self.page_size
        self.preferences.page_size = updated_page_size
        self.preferences.save()
        if self.search_query:
            self._resync_search(reset_scroll=True)
        else:
            self.current_page = min(
                first_visible_index // updated_page_size,
                self._total_pages() - 1,
            )
            self.refresh(reset_scroll=True)

