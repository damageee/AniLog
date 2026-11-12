"""空状态与对话框辅助。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)


def no_records_note(
    page: ft.Page,
    *,
    height: float = 60,
    width: float | None = None,
) -> ft.Container:
    fg = foreground_color(page)
    return ft.Container(
        width=width,
        height=height,
        alignment=ft.Alignment.CENTER,
        content=ui_text(
            "无记录",
            size=18,
            color=ft.Colors.with_opacity(0.45, fg),
        ),
    )


def confirmation_dialog(
    page: ft.Page,
    *,
    title: str,
    message: str,
    confirm_label: str,
    on_confirm: Callable[[ft.ControlEvent], None],
) -> ft.AlertDialog:
    text_color = foreground_color(page)

    def cancel(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    return ft.AlertDialog(
        modal=True,
        bgcolor=background_color(page),
        title=ui_text(title, color=text_color),
        content=ui_text(message, color=text_color),
        title_text_style=ui_text_style(color=text_color),
        content_text_style=ui_text_style(color=text_color),
        actions=[
            ft.Button(content=ui_text("取消"), on_click=cancel),
            ft.Button(content=ui_text(confirm_label), on_click=on_confirm),
        ],
    )


def show_error_dialog(page: ft.Page, *, title: str, message: str) -> None:
    text_color = foreground_color(page)

    def close(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text(title, color=text_color),
            content=ui_text(message, color=text_color),
            title_text_style=ui_text_style(color=text_color),
            content_text_style=ui_text_style(color=text_color),
            actions=[
                ft.Button(content=ui_text("关闭"), on_click=close),
            ],
        )
    )


def close_dialog(dialog: ft.AlertDialog) -> None:
    if dialog.open:
        dialog.open = False
        dialog.update()
