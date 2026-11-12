"""章节标题。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.colors import foreground_color
from bangumi.ui.theme import ui_text


def section_title(
    page: ft.Page,
    value: str,
    *,
    size: int = 15,
) -> ft.Text:
    return ui_text(
        value,
        size=size,
        weight=ft.FontWeight.BOLD,
        color=foreground_color(page),
    )
