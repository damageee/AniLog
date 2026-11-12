"""已阅页面 mixin：options。"""

from __future__ import annotations


import flet as ft

from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import (
    ui_text,
)

from bangumi.views.watched.constants import *

class OptionsMixin:
    def _options_row(self) -> ft.Column:
        mobile = is_compact_layout(self.page)

        def row(control: ft.Control) -> ft.Container:
            return ft.Container(
                height=32,
                alignment=(
                    ft.Alignment.CENTER
                    if mobile
                    else ft.Alignment.CENTER_LEFT
                ),
                content=control,
            )

        return ft.Column(
            spacing=5,
            horizontal_alignment=(
                ft.CrossAxisAlignment.CENTER
                if mobile
                else ft.CrossAxisAlignment.START
            ),
            controls=[
                row(
                    ft.Checkbox(
                        label=ui_text("合并同一部番"),
                        value=self.preferences.merge_same_anime,
                        visual_density=ft.VisualDensity.COMPACT,
                        height=32,
                        on_change=self._toggle_merge,
                    )
                ),
                row(
                    ft.Checkbox(
                        label=ui_text("高亮已公开续作"),
                        value=self.preferences.highlight_public_sequels,
                        visual_density=ft.VisualDensity.COMPACT,
                        height=32,
                        on_change=self._toggle_highlight_public_sequels,
                    )
                ),
                row(
                    ft.PopupMenuButton(
                        height=32,
                        content=ft.Row(
                            tight=True,
                            spacing=2,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                            controls=[
                                ft.Container(
                                    width=24,
                                    height=24,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(
                                        ft.Icons.ARROW_DROP_UP,
                                        size=22,
                                    ),
                                ),
                                ui_text("列可见性", size=14),
                            ],
                        ),
                        items=[
                            ft.PopupMenuItem(
                                content=ui_text(label),
                                checked=self.visible_columns.get(
                                    key, True
                                ),
                                on_click=lambda event, column=key: (
                                    self._toggle_column(column)
                                ),
                            )
                            for key, label in self._menu_columns()
                        ],
                    )
                ),
            ],
        )

    def _toggle_column(self, key: str) -> None:
        self.visible_columns[key] = not self.visible_columns.get(key, True)
        self.preferences.save()
        self._resync_search()

    def _toggle_merge(self, event: ft.ControlEvent) -> None:
        self.preferences.merge_same_anime = bool(event.control.value)
        self.preferences.save()
        if self.search_query:
            self._resync_search(reset_scroll=True, update_header=True)
        else:
            self.refresh(reset_scroll=True, update_header=True)

    def _toggle_highlight_public_sequels(
        self,
        event: ft.ControlEvent,
    ) -> None:
        self.preferences.highlight_public_sequels = bool(event.control.value)
        self.preferences.save()
        self.refresh()

