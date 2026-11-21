"""评分图表工具。"""

from __future__ import annotations

import time
from typing import Callable

import flet as ft
import flet.canvas as fcanvas

from bangumi.ui.colors import foreground_color
from bangumi.ui.events import is_hover
from bangumi.ui.interaction import tooltip_colors
from bangumi.ui.platform import is_mobile
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text
from bangumi.views.statistics.common.shared import (
    JOURNEY_BASELINE,
    JOURNEY_HEIGHT,
    JOURNEY_TOP,
)


def smooth_path_elements(points, *, move: bool = True):
    elements: list[fcanvas.Path.PathElement] = []
    if not points:
        return elements
    if move:
        elements.append(fcanvas.Path.MoveTo(points[0][0], points[0][1]))
    count = len(points)
    if count <= 2:
        if count == 2:
            elements.append(
                fcanvas.Path.LineTo(points[1][0], points[1][1])
            )
        return elements
    for index in range(count - 1):
        p0 = points[index - 1] if index > 0 else points[index]
        p1 = points[index]
        p2 = points[index + 1]
        p3 = points[index + 2] if index + 2 < count else p2
        cp1 = (
            p1[0] + (p2[0] - p0[0]) / 6,
            p1[1] + (p2[1] - p0[1]) / 6,
        )
        cp2 = (
            p2[0] - (p3[0] - p1[0]) / 6,
            p2[1] - (p3[1] - p1[1]) / 6,
        )
        elements.append(
            fcanvas.Path.CubicTo(
                cp1[0],
                cp1[1],
                cp2[0],
                cp2[1],
                p2[0],
                p2[1],
            )
        )
    return elements


def line_shapes(months, series, *, slot, limit=None):
    shapes: list[fcanvas.Shape] = []
    for values, color in series:
        count = (
            len(values)
            if limit is None
            else min(max(limit, 0), len(values))
        )
        points = [
            (
                index * slot + slot / 2,
                JOURNEY_BASELINE
                - values[index] / 100
                * (JOURNEY_BASELINE - JOURNEY_TOP),
            )
            for index in range(count)
            if values[index] > 0
        ]
        if len(points) >= 2:
            shapes.append(
                fcanvas.Path(
                    elements=smooth_path_elements(points),
                    paint=ft.Paint(
                        color=color,
                        stroke_width=2,
                        style=ft.PaintingStyle.STROKE,
                        stroke_cap=ft.StrokeCap.ROUND,
                    ),
                )
            )
    return shapes


def month_labels(
    keys: list[tuple[int, int]],
    *,
    slot: float,
    secondary: str,
    labels: list[str] | None = None,
) -> ft.Row:
    return ft.Row(
        width=max(1, len(keys)) * slot,
        spacing=0,
        controls=[
            ft.Container(
                width=slot,
                alignment=ft.Alignment.CENTER,
                content=ui_text(
                    (
                        labels[index]
                        if labels
                        else f"{keys[index][0]}.{keys[index][1]:02d}"
                    ),
                    size=8,
                    color=secondary,
                    no_wrap=True,
                ),
            )
            for index, key in enumerate(keys)
        ],
    )


def chart_stack(
    page: ft.Page,
    *,
    width: float,
    canvas: fcanvas.Canvas,
    count: int,
    text_at: Callable[[int], str],
    slot: float,
    on_tap: Callable[[int], None] | None = None,
) -> tuple[ft.Control, Callable[[], None]]:
    fg = foreground_color(page)
    mobile = is_mobile(page)
    tip_bg, tip_fg = tooltip_colors(page)
    label_text = ui_text(
        "",
        size=12,
        color=tip_fg,
        no_wrap=True,
    )
    label = ft.Container(
        visible=False,
        ignore_interactions=True,
        bgcolor=ft.Colors.with_opacity(0.95, tip_bg),
        border_radius=4,
        padding=ft.Padding.symmetric(
            horizontal=10,
            vertical=6,
        ),
        content=label_text,
    )
    shown_at = {"value": 0.0}
    active = {"index": -1}

    def render(index: int) -> None:
        text = text_at(index)
        if not text:
            return
        label_text.value = text
        lines = text.split("\n")
        label.width = max(
            text_width(line, size=12) for line in lines
        ) + 28
        left = index * slot
        label.left = max(
            0.0,
            min(left, width - label.width),
        )
        label.top = 4
        label.visible = True
        active["index"] = index
        try:
            label.update()
        except Exception:
            pass

    def refresh() -> None:
        index = active["index"]
        if index >= 0 and label.visible:
            render(index)

    def show(index: int) -> None:
        shown_at["value"] = time.monotonic()
        render(index)

    def hide(
        event: ft.ControlEvent | None = None,
        *,
        force: bool = False,
    ) -> None:
        if not force and time.monotonic() - shown_at["value"] < 0.2:
            return
        if not label.visible:
            return
        label.visible = False
        active["index"] = -1
        try:
            label.update()
        except Exception:
            pass

    def long_move(event: ft.ControlEvent, index: int) -> None:
        offset = getattr(event, "local_offset_from_origin", None)
        if offset is None:
            offset = getattr(event, "offset_from_origin", None)
        if offset is None:
            return
        dx = float(getattr(offset, "x", 0) or 0)
        target = index + int(round(dx / slot)) if slot else index
        target = max(0, min(count - 1, target))
        show(target)

    def make_hit(index: int) -> ft.Control:
        box = ft.Container(
            width=slot,
            height=JOURNEY_HEIGHT,
            bgcolor=ft.Colors.TRANSPARENT,
            on_hover=(
                (
                    lambda event, i=index: (
                        show(i)
                        if is_hover(event)
                        else hide(force=True)
                    )
                )
                if not mobile
                else None
            ),
        )
        # 命中块上的点击统一回调 index，悬浮/长按逻辑不变。
        if on_tap is not None:
            box.on_click = (
                lambda event, i=index: on_tap(i)
            )
        if not mobile:
            return box
        return ft.GestureDetector(
            width=slot,
            height=JOURNEY_HEIGHT,
            on_long_press_start=lambda event, i=index: show(i),
            on_long_press_move_update=(
                lambda event, i=index: long_move(event, i)
            ),
            on_long_press_end=lambda event: hide(force=True),
            on_long_press_cancel=lambda event: hide(force=True),
            content=box,
        )

    hits = ft.Row(
        width=width,
        height=JOURNEY_HEIGHT,
        spacing=0,
        controls=[make_hit(index) for index in range(count)],
    )
    stack = ft.Stack(
        width=width,
        height=JOURNEY_HEIGHT,
        clip_behavior=ft.ClipBehavior.NONE,
        controls=[canvas, hits, label],
    )
    return stack, refresh


def line_chart(
    page: ft.Page,
    keys,
    series,
    *,
    tooltips: Callable[[int], str] | None = None,
    limit: int | None = None,
    on_tap: Callable[[int], None] | None = None,
) -> tuple[ft.Control, Callable[..., None]]:
    count = len(keys)
    default_width = max(360.0, 44.0 * count)
    width = fit_chart_width(page, default_width)
    slot = width / max(1, count)
    canvas = fcanvas.Canvas(
        width=width,
        height=JOURNEY_HEIGHT,
        shapes=line_shapes(keys, series, slot=slot, limit=limit),
    )

    def redraw(new_limit: int | None = None) -> None:
        canvas.shapes = line_shapes(
            keys,
            series,
            slot=slot,
            limit=new_limit,
        )
        try:
            canvas.update()
        except Exception:
            pass

    if tooltips is None:
        chart: ft.Control = canvas
    else:
        chart, _ = chart_stack(
            page,
            width=width,
            canvas=canvas,
            count=count,
            text_at=tooltips,
            slot=slot,
            on_tap=on_tap,
        )
    return chart, redraw
