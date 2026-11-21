"""已阅页面 mixin：filters。"""

from __future__ import annotations

from collections import Counter

import flet as ft

from bangumi.io.importer import CATEGORY_OPTIONS
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import (
    Record,
    split_studios,
    split_tags,
)

from bangumi.views.watched.constants import *

class FilterMixin:
    def _active_filters(self) -> list[tuple[str, str]]:
        return [
            (mode, value)
            for mode, value in self.filters
            if mode and value
        ]

    def _filter_options(self, mode: str) -> list[str]:
        if mode == "category":
            return list(CATEGORY_OPTIONS)
        if mode == "rating":
            return list(FILTER_RATINGS)
        if mode == "tag":
            counter: Counter[str] = Counter()
            for record in self.records:
                counter.update(split_tags(record.get("tag")))
            return [
                name
                for name, _ in sorted(
                    counter.items(), key=lambda item: (-item[1], item[0])
                )
            ]
        if mode == "studio":
            counter = Counter()
            for record in self.records:
                counter.update(split_studios(record.get("studio")))
            return [
                name
                for name, _ in sorted(
                    counter.items(), key=lambda item: (-item[1], item[0])
                )
            ]
        if mode == "year":
            years = set()
            for record in self.records:
                date = earliest_broadcast_date(
                    str(record.get("broadcast") or "")
                )
                if date is not None:
                    years.add(date[0])
            return [str(year) for year in sorted(years, reverse=True)]
        return []

    def _record_matches(
        self,
        record: Record,
        mode: str,
        value: str,
    ) -> bool:
        if mode == "category":
            return str(record.get("category") or "").strip() == value
        if mode == "tag":
            return value in split_tags(record.get("tag"))
        if mode == "studio":
            return value in split_studios(record.get("studio"))
        if mode == "year":
            date = earliest_broadcast_date(
                str(record.get("broadcast") or "")
            )
            return date is not None and str(date[0]) == value
        if mode == "rating":
            text = str(record.get("rating") or "").strip()
            if not text.isdigit():
                return False
            score = int(text)
            if not 0 <= score <= 100:
                return False
            if value == "90+":
                return score >= 90
            if value == "0~49":
                return score <= 49
            low, high = value.split("~")
            return int(low) <= score <= int(high)
        return True

    def _filtered_records(self) -> list[Record]:
        active = self._active_filters()
        if not active:
            return self.records
        return [
            record
            for record in self.records
            if all(
                self._record_matches(record, mode, value)
                for mode, value in active
            )
        ]

    def _refresh_filter_ui_and_table(self) -> None:
        self._render_filters()
        active = self._active_filters()
        if active == self._applied_filters:
            return
        self._applied_filters = active
        self.current_page = 0
        # 同时刷新工具栏 chips。
        self.refresh(reset_scroll=True, update_header=True)

    def _change_filter_mode(self, index: int, mode: str) -> None:
        if not 0 <= index < len(self.filters):
            return
        self.filters[index][0] = str(mode or "")
        self.filters[index][1] = ""
        self._refresh_filter_ui_and_table()

    def _change_filter_value(self, index: int, value: str) -> None:
        if not 0 <= index < len(self.filters):
            return
        self.filters[index][1] = str(value or "")
        self._refresh_filter_ui_and_table()

    def _add_filter(self, event: ft.ControlEvent) -> None:
        if any(not mode or not value for mode, value in self.filters):
            return
        self.filters.append(["", ""])
        self._refresh_filter_ui_and_table()

    def _clear_filters(self, event: ft.ControlEvent) -> None:
        if not self.filters:
            return
        self.filters = []
        self._refresh_filter_ui_and_table()

    def _filter_section(self) -> ft.Control:
        self._render_filters()
        return self.filter_column

    def _render_filters(self) -> None:
        mobile = is_compact_layout(self.page)
        rows: list[ft.Control] = []
        for index, (mode, value) in enumerate(self.filters):
            mode_dropdown = ft.Dropdown(
                value=mode or None,
                hint_text="筛选条件",
                options=[
                    ft.DropdownOption(key=key, text=text)
                    for key, text in FILTER_MODES
                ],
                width=200,
                on_select=(
                    lambda event, i=index: (
                        self._change_filter_mode(i, event.control.value)
                    )
                ),
            )
            controls: list[ft.Control] = [
                ui_text(f"条件{index + 1}", size=13),
                mode_dropdown,
            ]
            if mode:
                controls.append(
                    ft.Dropdown(
                        value=value or None,
                        options=[
                            ft.DropdownOption(key=option, text=option)
                            for option in self._filter_options(mode)
                        ],
                        width=200,
                        on_select=(
                            lambda event, i=index: (
                                self._change_filter_value(
                                    i,
                                    event.control.value,
                                )
                            )
                        ),
                    )
                )
            rows.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=controls,
                )
            )
        button_row = ft.Row(
            tight=True,
            spacing=8,
            alignment=(
                ft.MainAxisAlignment.CENTER
                if mobile
                else ft.MainAxisAlignment.START
            ),
            controls=[
                ft.Button(
                    content=ui_text("添加筛选"),
                    expand=True,
                    height=40,
                    on_click=self._add_filter,
                ),
                ft.Button(
                    content=ui_text("清空筛选"),
                    expand=True,
                    height=40,
                    on_click=self._clear_filters,
                ),
            ],
        )
        filter_controls: list[ft.Control] = [button_row]
        if not self.filters:
            filter_controls.append(
                ui_text(
                    "无筛选",
                    size=11,
                    color=ft.Colors.with_opacity(
                        0.55,
                        foreground_color(self.page),
                    ),
                )
            )
        button_group = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            controls=filter_controls,
        )
        self.filter_column.controls = [
            (
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[button_group],
                )
                if mobile
                else button_group
            ),
            *rows,
        ]
        try:
            self.filter_column.update()
        except Exception:
            pass

