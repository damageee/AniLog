"""Add page for the 已追 watchlist."""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
)


def build_append_from_text_view(
    page: ft.Page,
    title: str,
    *,
    on_confirm: Callable[[str], None],
    on_cancel: Callable[[], None],
    route: str,
) -> ft.View:
    """Build the multi-line 追番 add page."""
    foreground = foreground_color(page)
    field = ft.TextField(
        expand=True,
        multiline=True,
        min_lines=1,
        max_lines=None,
        autofocus=True,
        hint_text="每行一个名称",
        hint_style=ui_text_style(color=foreground, size=13),
        text_style=ui_text_style(color=foreground, size=14),
        border_color=ft.Colors.with_opacity(0.35, foreground),
        focused_border_color=ft.Colors.BLUE,
        border_radius=8,
        border=ft.OutlineInputBorder(border_radius=8),
        content_padding=ft.Padding.symmetric(
            horizontal=12,
            vertical=12,
        ),
    )

    def confirm(event: ft.ControlEvent) -> None:
        on_confirm(field.value or "")

    return ft.View(
        route=route,
        appbar=ft.AppBar(title=ui_text(title)),
        padding=page_padding(),
        controls=[
            ft.Column(
                expand=True,
                spacing=12,
                controls=[
                    field,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                        controls=[
                            ft.Button(
                                content=ui_text(
                                    "确认",
                                    color=ft.Colors.WHITE,
                                ),
                                bgcolor=ft.Colors.BLUE,
                                on_click=confirm,
                            ),
                            ft.OutlinedButton(
                                content=ui_text(
                                    "取消",
                                    color=foreground,
                                ),
                                style=ft.ButtonStyle(
                                    color=foreground,
                                    side=ft.BorderSide(
                                        1,
                                        ft.Colors.with_opacity(
                                            0.35,
                                            foreground,
                                        ),
                                    ),
                                    shape=ft.RoundedRectangleBorder(
                                        radius=8
                                    ),
                                    padding=ft.Padding.symmetric(
                                        horizontal=18,
                                        vertical=12,
                                    ),
                                ),
                                on_click=lambda event: on_cancel(),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
