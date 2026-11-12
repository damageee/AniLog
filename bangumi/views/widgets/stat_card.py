"""统计页 KPI 卡片。"""

from __future__ import annotations

from typing import Callable, Sequence

import flet as ft
from bangumi.ui.anim import animation

from bangumi.ui.colors import (
    foreground_color,
    is_dark,
    secondary_color,
)
from bangumi.ui.constants import (
    ANIM_SLOW_MS,
    HOVER_SCALE_CARD,
)
from bangumi.ui.events import is_hover
from bangumi.ui.theme import ui_text

Number = tuple[int, str]


def _number_group(
    page: ft.Page,
    value: ft.Text,
    unit: str,
) -> ft.Row:
    return ft.Row(
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.END,
        controls=[
            value,
            ui_text(
                unit,
                size=11,
                color=ft.Colors.with_opacity(
                    0.72,
                    foreground_color(page),
                ),
            ),
        ],
    )


def stat_card(
    page: ft.Page,
    title: str,
    value: str | Sequence[Number],
    *,
    accent: str | None = None,
    expand: int | None = 1,
    clickable: bool = False,
    on_click: Callable[[ft.ControlEvent], None] | None = None,
    compact: bool = False,
    layout: str = "row",
    animated: list[tuple[ft.Text, int]] | None = None,
    height: int | None = None,
) -> ft.Container:
    """构建 KPI 卡片。

    ``layout`` 选择主体：``row``（标题与值并排）、
    ``column``（标题在值上方）或 ``numbers``（一个或多个带动画的
    数字；此时 ``value`` 为 ``(number, unit)`` 序列）。
    """
    color = accent or ("#60A5FA" if is_dark(page) else "#2563EB")
    fg = foreground_color(page)
    if compact:
        vertical = 6
    else:
        vertical = {"numbers": 6, "column": 12}.get(layout, 10)

    if layout == "numbers":
        groups: list[ft.Row] = []
        numbers = value if isinstance(value, (list, tuple)) else ()
        for target, unit in numbers:
            number = ui_text(
                "0",
                size=24,
                weight=ft.FontWeight.BOLD,
                color=color,
            )
            if animated is not None:
                animated.append((number, target))
            groups.append(_number_group(page, number, unit))
        body: ft.Control = ft.Column(
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ui_text(
                    title,
                    size=13,
                    color=ft.Colors.with_opacity(0.8, fg),
                ),
                ft.Row(spacing=18, controls=groups),
            ],
        )
    elif layout == "column":
        body = ft.Column(
            spacing=4,
            controls=[
                ui_text(
                    title,
                    size=13,
                    color=ft.Colors.with_opacity(0.72, fg),
                ),
                ui_text(
                    str(value),
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                ),
            ],
        )
    else:
        body = ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ui_text(
                    title,
                    size=13,
                    color=secondary_color(page, 0.65),
                    no_wrap=True,
                ),
                ui_text(
                    str(value),
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                    no_wrap=True,
                ),
            ],
        )

    card = ft.Container(
        height=height,
        expand=expand,
        padding=ft.Padding.symmetric(
            horizontal=16,
            vertical=vertical,
        ),
        border_radius=14,
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.38, color),
        ),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
            colors=[
                ft.Colors.with_opacity(0.13, color),
                ft.Colors.with_opacity(0.03, color),
            ],
        ),
        on_click=on_click if clickable else None,
        content=body,
    )
    if clickable:
        card.scale = ft.Scale(1.0)
        card.animate_scale = animation(
            ANIM_SLOW_MS,
            ft.AnimationCurve.EASE_OUT,
        )

        def on_hover(event: ft.ControlEvent) -> None:
            hovered = is_hover(event)
            card.scale = ft.Scale(
                HOVER_SCALE_CARD if hovered else 1.0
            )
            card.update()

        card.on_hover = on_hover

        def card_long_start(event: ft.ControlEvent) -> None:
            card.scale = ft.Scale(HOVER_SCALE_CARD)
            try:
                card.update()
            except Exception:
                pass

        def card_long_end(event: ft.ControlEvent) -> None:
            card.scale = ft.Scale(1.0)
            try:
                card.update()
            except Exception:
                pass

        return ft.GestureDetector(
            expand=expand,
            on_long_press_start=card_long_start,
            on_long_press_end=card_long_end,
            on_long_press_cancel=card_long_end,
            content=card,
        )
    return card
