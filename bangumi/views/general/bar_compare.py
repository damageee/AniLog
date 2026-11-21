"""左右对照的横条竞赛模板页。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.anim import animation
from bangumi.ui.colors import foreground_color
from bangumi.ui.constants import ANIM_BASE_MS, HOVER_SCALE_BAR
from bangumi.ui.events import is_hover
from bangumi.ui.feedback import no_records_note
from bangumi.ui.interaction import back_icon, hover_icon
from bangumi.ui.layout import page_padding, vertical_page
from bangumi.ui.platform import is_mobile
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import go_back
from bangumi.views.navigation.stack import register_resize_handler

from .bar_chart import random_bar_colors

__all__ = ["build_bar_compare_view"]


def build_bar_compare_view(
    page: ft.Page,
    name_l: str,
    arr_l: list[tuple[str, float, float]],
    name_r: str,
    arr_r: list[tuple[str, float, float]],
    *,
    hide_score: bool = False,
    title: str = "",
    route: str | None = None,
    decimals: int = 2,
    on_bar_click_l: Callable[[str], None] | None = None,
    on_bar_click_r: Callable[[str], None] | None = None,
    remark: str = "",
    rebuild: Callable[[], ft.View] | None = None,
) -> ft.View:
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    gap = 16.0
    divider_w = 1.0
    holder: dict[str, ft.View] = {}

    def total_width() -> float:
        return max(320.0, float(page.width or 1000) - 48.0)

    def half_width() -> float:
        return max(
            80.0,
            (total_width() - divider_w - gap * 2) / 2,
        )

    def fmt(value: float) -> str:
        if decimals > 0:
            return f"{value:.{decimals}f}"
        return str(int(round(value)))

    def side_reserve(arr: list[tuple[str, float, float]]) -> float:
        if hide_score:
            return 12.0
        return max(
            text_width("00000000", size=12),
            max(
                (text_width(fmt(value), size=12) for _, value, _ in arr),
                default=0.0,
            ),
        ) + 12.0

    def bar_width(
        value: float,
        maximum: float,
        avail: float,
    ) -> float:
        if value <= 0 or maximum <= 0:
            return 0.0
        return max(4.0, avail * min(1.0, value / maximum))

    def back(event: ft.ControlEvent) -> None:
        if route:
            go_back(page, route)
            return
        current = holder.get("view")
        if current is not None and current in page.views:
            page.views.remove(current)
        page.update()

    def build_appbar() -> ft.AppBar:
        leading = (
            back_icon(page, route)
            if route
            else hover_icon(
                page,
                ft.Icons.ARROW_BACK,
                on_click=back,
                tooltip="返回",
                padding=8,
            )
        )
        return ft.AppBar(
            title=ui_text(title or f"{name_l} × {name_r}"),
            automatically_imply_leading=False,
            leading=leading,
        )

    if not arr_l and not arr_r:
        view = ft.View(
            route=route,
            appbar=build_appbar(),
            padding=page_padding(),
            controls=[
                vertical_page(
                    [
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                no_records_note(
                                    page,
                                    height=60,
                                    width=max(
                                        200.0,
                                        float(page.width or 1000) - 48,
                                    ),
                                )
                            ],
                        )
                    ]
                )
            ],
        )
        holder["view"] = view
        if rebuild is not None:
            view.data = {"rebuild": rebuild}
        return view

    max_len = max(len(arr_l), len(arr_r))
    colors = random_bar_colors(max_len)
    reserve_l = side_reserve(arr_l)
    reserve_r = side_reserve(arr_r)
    bars_l: list[tuple[ft.Container, float, float]] = []
    bars_r: list[tuple[ft.Container, float, float]] = []

    def hover_bar(bar: ft.Container, event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        bar.scale = HOVER_SCALE_BAR if hovered else 1.0
        try:
            bar.update()
        except Exception:
            pass

    def side_item(
        side: str,
        label: str,
        value: float,
        maximum: float,
        avail: float,
        index: int,
        on_click: Callable[[str], None] | None,
    ) -> ft.Control:
        bw = bar_width(value, maximum, avail)
        bar = ft.Container(
            width=bw,
            height=22,
            border_radius=4,
            bgcolor=colors[index],
        )
        bar.animate_scale = animation(
            ANIM_BASE_MS,
            ft.AnimationCurve.EASE_OUT,
        )
        bar.scale = 1.0
        text_w = (
            0.0
            if hide_score
            else float(text_width(fmt(value), size=12))
        )
        full = avail
        # 命中区取柱子实际长度；只有短于 1/4 完整宽度时才扩大。
        hit_width = bw if bw >= full / 4.0 else full / 4.0
        row_width = max(
            hit_width,
            bw + (8.0 + text_w if text_w else 0.0),
        )
        hit_layer = ft.Container(
            width=hit_width,
            height=22,
            bgcolor=ft.Colors.TRANSPARENT,
            tooltip=None if is_mobile(page) else label,
            on_hover=lambda event, b=bar: hover_bar(b, event),
            on_click=(
                (lambda event, n=label: on_click(n))
                if on_click is not None
                else None
            ),
        )
        if side == "l":
            bars_l.append((bar, value, maximum))
            hit_layer.left = 0.0
            stack_controls: list[ft.Control] = [bar, hit_layer]
            if not hide_score:
                # 分值文字绝对定位，不参与命中。
                stack_controls.append(
                    ft.Container(
                        left=bw + 8.0,
                        top=0,
                        height=22,
                        ignore_interactions=True,
                        alignment=ft.Alignment.CENTER_LEFT,
                        content=ui_text(fmt(value), size=12, color=fg),
                    )
                )
            bar_row = ft.Stack(
                width=row_width,
                height=22,
                clip_behavior=ft.ClipBehavior.NONE,
                controls=stack_controls,
            )
            name_row = ft.Row(
                controls=[
                    ui_text(
                        label,
                        size=11,
                        color=secondary,
                        no_wrap=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                ],
            )
        else:
            bars_r.append((bar, value, maximum))
            # 右侧镜像：柱子贴右，命中区与文字按右边界定位。
            bar.left = row_width - bw
            hit_layer.left = row_width - hit_width
            stack_controls = [hit_layer, bar]
            if not hide_score:
                stack_controls.append(
                    ft.Container(
                        left=max(
                            0.0,
                            row_width - bw - 8.0 - text_w,
                        ),
                        top=0,
                        height=22,
                        ignore_interactions=True,
                        alignment=ft.Alignment.CENTER_LEFT,
                        content=ui_text(fmt(value), size=12, color=fg),
                    )
                )
            bar_row = ft.Stack(
                width=row_width,
                height=22,
                clip_behavior=ft.ClipBehavior.NONE,
                controls=stack_controls,
            )
            name_row = ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ui_text(
                        label,
                        size=11,
                        color=secondary,
                        no_wrap=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                ],
            )
        return ft.Container(
            width=half_width(),
            height=38,
            alignment=(
                ft.Alignment.CENTER_LEFT
                if side == "l"
                else ft.Alignment.CENTER_RIGHT
            ),
            content=ft.Column(
                spacing=2,
                horizontal_alignment=(
                    ft.CrossAxisAlignment.START
                    if side == "l"
                    else ft.CrossAxisAlignment.END
                ),
                controls=[bar_row, name_row],
            ),
        )

    def build_side(
        side: str,
        name: str,
        arr: list[tuple[str, float, float]],
        reserve: float,
        on_click: Callable[[str], None] | None,
    ) -> ft.Column:
        avail = max(40.0, half_width() - reserve)
        items: list[ft.Control] = []
        for index in range(max_len):
            if index >= len(arr):
                items.append(ft.Container(height=38))
                continue
            label, value, maximum = arr[index]
            items.append(
                side_item(
                    side,
                    label,
                    value,
                    maximum,
                    avail,
                    index,
                    on_click,
                )
            )
        horizontal = (
            ft.CrossAxisAlignment.START
            if side == "l"
            else ft.CrossAxisAlignment.END
        )
        if not arr:
            items = [ui_text("—", size=13, color=fg)]
        return ft.Column(
            width=half_width(),
            spacing=0,
            horizontal_alignment=horizontal,
            controls=[
                ft.Row(
                    width=half_width(),
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ui_text(
                            name,
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=fg,
                        )
                    ],
                ),
                ft.Container(height=6),
                ft.Column(
                    spacing=10,
                    horizontal_alignment=horizontal,
                    controls=items,
                ),
            ],
        )

    left_col = build_side("l", name_l, arr_l, reserve_l, on_bar_click_l)
    right_col = build_side("r", name_r, arr_r, reserve_r, on_bar_click_r)
    body = ft.Row(
        width=total_width(),
        spacing=gap,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            left_col,
            ft.Container(
                width=divider_w,
                bgcolor=ft.Colors.with_opacity(0.25, fg),
            ),
            right_col,
        ],
    )

    if remark:
        note = ft.Container(
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.only(top=8),
            content=ui_text(
                remark,
                size=11,
                color=ft.Colors.with_opacity(0.55, fg),
                text_align=ft.TextAlign.CENTER,
            ),
        )
        content_controls: list[ft.Control] = [body, note]
    else:
        content_controls = [body]

    view = ft.View(
        route=route,
        appbar=build_appbar(),
        padding=page_padding(),
        controls=[vertical_page(content_controls)],
    )
    holder["view"] = view

    def on_resize(event: ft.ControlEvent) -> None:
        # 仅栈顶响应
        if view not in page.views or page.views[-1] is not view:
            return
        changed = False
        width = total_width()
        half = half_width()
        if abs(float(body.width or 0) - width) > 1:
            body.width = width
            changed = True
        for column in (left_col, right_col):
            if abs(float(column.width or 0) - half) > 1:
                column.width = half
                changed = True
        for bars, reserve in (
            (bars_l, reserve_l),
            (bars_r, reserve_r),
        ):
            available = max(40.0, half - reserve)
            for bar, value, maximum in bars:
                new_width = bar_width(
                    value, maximum, available
                )
                if abs(float(bar.width or 0) - new_width) > 1:
                    bar.width = new_width
                    changed = True
        if changed:
            try:
                body.update()
            except Exception:
                pass

    if route:
        register_resize_handler(page, route, on_resize)
    if rebuild is not None:
        view.data = {"rebuild": rebuild}
    return view
