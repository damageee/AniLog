"""主题颜色辅助。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.constants import (
    LINK_HOVER_DARK,
    LINK_HOVER_LIGHT,
)


def is_dark(page: ft.Page) -> bool:
    return page.theme_mode == ft.ThemeMode.DARK


def foreground_color(page: ft.Page) -> str:
    return ft.Colors.WHITE if is_dark(page) else ft.Colors.BLACK


def background_color(page: ft.Page) -> str:
    return ft.Colors.BLACK if is_dark(page) else ft.Colors.WHITE


def secondary_color(page: ft.Page, opacity: float = 0.55) -> str:
    return ft.Colors.with_opacity(opacity, foreground_color(page))


def link_hover_color(page: ft.Page) -> str:
    return (
        LINK_HOVER_DARK
        if page.theme_mode == ft.ThemeMode.DARK
        else LINK_HOVER_LIGHT
    )
