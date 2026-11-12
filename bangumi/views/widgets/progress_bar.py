"""通用进度行与进度条。"""

from __future__ import annotations

import flet as ft

from bangumi.core.utils import percent
from bangumi.ui.colors import foreground_color
from bangumi.ui.constants import PROGRESS_COLOR
from bangumi.ui.theme import ui_text


def build_stats_row(
    done: int,
    total: int,
    *,
    size: int = 16,
) -> ft.Row:
    value = percent(done, total)
    return ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ui_text(f"{done}/{total}", size=size),
            ui_text(f"{value:.1f}%", size=size),
        ],
    )


def build_progress_bar(
    page: ft.Page,
    done: int,
    total: int,
    *,
    height: int = 12,
    radius: int = 6,
    color: str | None = None,
) -> ft.ProgressBar:
    foreground = foreground_color(page)
    return ft.ProgressBar(
        value=percent(done, total) / 100,
        height=height,
        bar_height=height,
        color=color or PROGRESS_COLOR,
        bgcolor=ft.Colors.with_opacity(0.15, foreground),
        border_radius=radius,
    )


def build_progress_block(
    page: ft.Page,
    done: int,
    total: int,
    *,
    size: int = 16,
    height: int = 12,
    radius: int = 6,
    color: str | None = None,
) -> list[ft.Control]:
    return [
        build_stats_row(done, total, size=size),
        build_progress_bar(
            page,
            done,
            total,
            height=height,
            radius=radius,
            color=color,
        ),
    ]
