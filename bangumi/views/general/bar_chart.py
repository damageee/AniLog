"""可复用的水平条形图页面。

``build_bar_chart_view`` 将 ``(name, value)`` 对渲染为水平条形，
按值排序（默认降序，``reverse`` 时为升序）。条形会按当前
窗口宽度缩放，并在尺寸变化时刷新。``max_value`` 覆盖缩放上限，
``title`` 设置应用栏文本，``route`` 设置视图路由。
"""

from __future__ import annotations

import colorsys
import random
from typing import Callable

import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover

from bangumi.ui.tag_colors import PALETTE
from bangumi.ui.theme import ui_text
from bangumi.ui.text_metrics import text_width
from bangumi.ui.interaction import (
    FloatingLabel,
    back_icon,
    hover_icon,
)
from bangumi.ui.platform import is_mobile
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.views.navigation import (
    go_back,
)
from bangumi.ui.feedback import (
    no_records_note,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.ui.constants import (
    ANIM_BASE_MS,
    HOVER_SCALE_BAR,
)

__all__ = ["build_bar_chart_view", "random_bar_colors"]


def random_bar_colors(total: int) -> list[str]:
    total = max(0, int(total))
    used: set[str] = set()
    colors: list[str] = []
    attempts = 0
    limit = max(40, total * 40)
    while len(colors) < total and attempts < limit:
        attempts += 1
        hue = random.random()
        saturation = random.uniform(0.45, 0.70)
        value = random.uniform(0.75, 0.95)
        red, green, blue = colorsys.hsv_to_rgb(
            hue, saturation, value
        )
        color = "#{:02X}{:02X}{:02X}".format(
            int(round(red * 255)),
            int(round(green * 255)),
            int(round(blue * 255)),
        )
        if color in used:
            continue
        used.add(color)
        colors.append(color)
    while len(colors) < total:
        colors.append(PALETTE[len(colors) % len(PALETTE)])
    return colors


def build_bar_chart_view(
    page: ft.Page,
    arr: list[tuple[str, int]],
    *,
    max_value: float | None = None,
    reverse: bool = False,
    title: str = "",
    route: str | None = None,
    decimals: int = 0,
    on_bar_click: Callable[[str], None] | None = None,
    on_bar_long_press: Callable[[str], None] | None = None,
    remark: str = "",
    rebuild: Callable[[], ft.View] | None = None,
) -> ft.View:
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    entries = [
        (float(value), str(name))
        for name, value in arr
    ]
    entries.sort(
        key=lambda item: (
            item[0] if reverse else -item[0],
            item[1],
        )
    )

    holder: dict[str, ft.View] = {}

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
            title=ui_text(title),
            automatically_imply_leading=False,
            leading=leading,
        )

    if not entries:
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
    top = max_value
    if top is None:
        top = max((value for value, _ in entries), default=0)
    if top <= 0:
        top = 1

    display_texts = [
        (
            f"{value:.{decimals}f}"
            if decimals > 0
            else str(int(round(value)))
        )
        for value, _ in entries
    ]
    reserve = max(
        text_width("00000000", size=12),
        max(
            (text_width(t, size=12) for t in display_texts),
            default=0.0,
        ),
    ) + 12.0

    def available_width() -> float:
        page_w = float(page.width or 1000)
        return max(40.0, page_w - 48.0 - reserve)

    bars: list[tuple[ft.Container, float]] = []
    bar_label = FloatingLabel(page)
    active_bar: dict[str, ft.Container | None] = {"bar": None}
    pitch = 48.0

    def scale_bar(target: ft.Container, on: bool) -> None:
        target.scale = HOVER_SCALE_BAR if on else 1.0
        try:
            target.update()
        except Exception:
            pass
    items: list[ft.Control] = []
    colors = random_bar_colors(len(entries))
    for index, (value, name) in enumerate(entries):
        if value <= 0:
            bar_width = 0.0
        elif value >= top:
            bar_width = available_width()
        else:
            bar_width = max(4.0, available_width() * value / top)
        bar = ft.Container(
            width=bar_width,
            height=22,
            border_radius=4,
            bgcolor=colors[index],
        )
        bar.animate_scale = animation(
            ANIM_BASE_MS, ft.AnimationCurve.EASE_OUT
        )
        bar.scale = 1.0

        def on_bar_hover(
            event: ft.ControlEvent,
            target=bar,
        ) -> None:
            hovered = is_hover(event)
            target.scale = HOVER_SCALE_BAR if hovered else 1.0
            try:
                target.update()
            except Exception:
                pass

        bar.on_hover = on_bar_hover
        bar.on_click = (
            lambda event, n=name: on_bar_click(n)
            if on_bar_click is not None
            else None
        )
        bar.tooltip = None if is_mobile(page) else name
        bars.append((bar, value))
        display_value = display_texts[index]
        column = ft.Column(
            spacing=2,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=(
                        ft.CrossAxisAlignment.CENTER
                    ),
                    controls=[
                        bar,
                        ui_text(display_value, size=12, color=fg),
                    ],
                ),
                ui_text(
                    name,
                    size=11,
                    color=secondary,
                    no_wrap=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
        )
        def show_name(
            event: ft.ControlEvent,
            display_name: str = name,
            bar_index: int = index,
        ) -> None:
            bar_label.show(event, display_name)
            scale_bar(bars[bar_index][0], True)
            active_bar["bar"] = bars[bar_index][0]

        def move_name(
            event: ft.ControlEvent,
            base_index: int = index,
        ) -> None:
            offset = getattr(event, "local_offset_from_origin", None)
            if offset is None:
                offset = getattr(event, "offset_from_origin", None)
            if offset is None:
                return
            dy = float(getattr(offset, "y", 0) or 0)
            target = base_index + int(round(dy / pitch))
            target = max(0, min(len(entries) - 1, target))
            current = active_bar["bar"]
            if current is not None:
                scale_bar(current, False)
            bar_label.show(event, entries[target][1])
            scale_bar(bars[target][0], True)
            active_bar["bar"] = bars[target][0]

        def end_long(event: ft.ControlEvent) -> None:
            current = active_bar["bar"]
            if current is not None:
                scale_bar(current, False)
            active_bar["bar"] = None
            bar_label.hide()

        item: ft.Control = ft.GestureDetector(
            on_long_press_start=show_name,
            on_long_press_move_update=move_name,
            on_long_press_end=end_long,
            on_long_press_cancel=end_long,
            on_double_tap=(
                lambda event, n=name: on_bar_long_press(n)
                if on_bar_long_press is not None
                else None
            ),
            content=ft.Container(
                height=38,
                content=column,
            ),
        )
        items.append(item)

    holder_column = ft.Column(spacing=10, controls=items)
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
        content_controls: list[ft.Control] = [holder_column, note]
    else:
        content_controls = [holder_column]
    view = ft.View(
        route=route,
        appbar=build_appbar(),
        padding=page_padding(),
        controls=[vertical_page(content_controls)],
    )
    holder["view"] = view

    previous_resize = page.on_resize

    def on_resize(event: ft.ControlEvent) -> None:
        if view in page.views and page.views[-1] is view:
            width = available_width()
            changed = False
            for bar, value in bars:
                if value <= 0:
                    new_width = 0.0
                elif value >= top:
                    new_width = width
                else:
                    new_width = max(4.0, width * value / top)
                if abs(float(bar.width or 0) - new_width) > 1:
                    bar.width = new_width
                    changed = True
            if changed:
                try:
                    holder_column.update()
                except Exception:
                    pass
        if previous_resize is not None:
            previous_resize(event)

    page.on_resize = on_resize
    if rebuild is not None:
        view.data = {"rebuild": rebuild}
    return view
