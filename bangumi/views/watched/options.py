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
                        label=ui_text("高亮已公开续作"),
                        value=self.preferences.highlight_public_sequels,
                        visual_density=ft.VisualDensity.COMPACT,
                        height=32,
                        on_change=self._toggle_highlight_public_sequels,
                    )
                ),
            ],
        )

    def _toggle_highlight_public_sequels(
        self,
        event: ft.ControlEvent,
    ) -> None:
        self.preferences.highlight_public_sequels = bool(event.control.value)
        self.preferences.save()
        self.refresh()
