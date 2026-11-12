"""统计页面通用工具、样式辅助与布局常量。"""

from __future__ import annotations

import math
from typing import (
    Callable,
)
import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover
from bangumi.ui.platform import is_desktop, is_mobile
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.interaction import FloatingLabel
from bangumi.ui.colors import (
    background_color,
    foreground_color,
    is_dark,
)
from bangumi.views.templates.page_shell import (
    make_view,
)
from bangumi.ui import scroll_memory
from bangumi.ui.feedback import (
    no_records_note,
)
from bangumi.views.navigation import (
    push_view,
)
from bangumi.ui.constants import (
    HOVER_SCALE_CHIP,
)


ANIMATION_SECONDS = 0.8


ANIMATION_STEPS = 36


CARD_HEIGHT = 70


RING_SIZE = 72


RING_STROKE = 7


PANEL_WIDTH = 190


COMPACT_PANEL_WIDTH = 154


PANEL_OFFSET = 14


OVERLAY_MARGIN = 10


PANEL_BOTTOM_RESERVE = 20


PANEL_SIDE_RESERVE = 12


BOTTOM_SAFE_MARGIN = 48.0


CHART_HEIGHT = 230


CHART_SLOT = 26


CHART_BAR_WIDTH = 18


CHART_MAX_BAR = 174


HEAT_SIZE = 34


JOURNEY_HEIGHT = 200


JOURNEY_BASELINE = 172


JOURNEY_TOP = 14


CAL_CELL = 11


CAL_GAP = 2


CAL_WEEKDAY_WIDTH = 20


TAG_ROW_SPACING = 8


TAG_BAR_HEIGHT = 8


TAG_DISPLAY_LIMIT = 16


TAG_DISPLAY_HEAD = 14


_CARD_COLORS = (
    ("#2563EB", "#60A5FA"),
    ("#059669", "#34D399"),
    ("#D97706", "#FBBF24"),
    ("#7C3AED", "#A78BFA"),
    ("#DB2777", "#F472B6"),
)


_SEGMENT_COLORS = (
    ("TV", "#D97706", "#FBBF24"),
    ("OVA", "#0D9488", "#2DD4BF"),
    ("OAD", "#4F46E5", "#818CF8"),
    ("SP", "#0284C7", "#38BDF8"),
    ("电影", "#7C3AED", "#A78BFA"),
    ("剧场版", "#DB2777", "#F472B6"),
)


_CATEGORY_COLORS = {
    "小说改": ("#2563EB", "#60A5FA"),
    "漫画改": ("#7C3AED", "#A78BFA"),
    "原创": ("#059669", "#34D399"),
    "游戏改": ("#D97706", "#FBBF24"),
    "电影": ("#DB2777", "#F472B6"),
    "音乐衍生": ("#0D9488", "#2DD4BF"),
    "跨媒体": ("#4F46E5", "#818CF8"),
    "其他": ("#64748B", "#94A3B8"),
}


def _accent(page: ft.Page, light: str, dark: str) -> str:
    return dark if is_dark(page) else light


def _type_chip(
    page: ft.Page,
    *,
    label: str,
    count: int,
    color: str,
    on_click: Callable[[ft.ControlEvent], None],
) -> ft.Control:
    text_color = foreground_color(page)
    chip_label = FloatingLabel(page)
    chip = ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.08, color),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.22, color),
        ),
        on_click=on_click,
        tooltip=(
            None if is_mobile(page) else f"查看{label}明细"
        ),
        scale=ft.Scale(1.0),
        animate_scale=animation(
            140,
            ft.AnimationCurve.EASE_OUT,
        ),
        content=ft.Row(
            spacing=4,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ui_text(
                    label,
                    size=11,
                    color=ft.Colors.with_opacity(0.78, text_color),
                ),
                ft.Row(
                    spacing=3,
                    controls=[
                        ui_text(
                            str(count),
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=color,
                        ),
                        ui_text("话", size=10, color=color),
                        ft.Icon(
                            icon=ft.Icons.CHEVRON_RIGHT,
                            size=12,
                            color=color,
                        ),
                    ],
                ),
            ],
        ),
    )

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        chip.scale = ft.Scale(
            HOVER_SCALE_CHIP if hovered else 1.0
        )
        chip.bgcolor = ft.Colors.with_opacity(
            0.16 if hovered else 0.08,
            color,
        )
        chip.update()

    chip.on_hover = on_hover

    def show_chip(event: ft.ControlEvent) -> None:
        chip_label.show(event, f"查看{label}明细")
        chip.scale = ft.Scale(HOVER_SCALE_CHIP)
        chip.bgcolor = ft.Colors.with_opacity(0.16, color)
        try:
            chip.update()
        except Exception:
            pass

    def end_chip(event: ft.ControlEvent) -> None:
        chip.scale = ft.Scale(1.0)
        chip.bgcolor = ft.Colors.with_opacity(0.08, color)
        try:
            chip.update()
        except Exception:
            pass
        chip_label.hide()

    return ft.GestureDetector(
        expand=True,
        on_long_press_start=show_chip,
        on_long_press_end=end_chip,
        on_long_press_cancel=end_chip,
        content=chip,
    )


def _segmented_ring(
    page: ft.Page,
    *,
    segments: tuple[tuple[str, int, str], ...],
    rings: list[tuple[ft.ProgressRing, float]],
) -> ft.Control:
    total = sum(count for _, count, _ in segments) or 1
    controls: list[ft.Control] = [
        ft.ProgressRing(
            value=1,
            width=RING_SIZE,
            height=RING_SIZE,
            stroke_width=RING_STROKE,
            color=ft.Colors.TRANSPARENT,
            bgcolor=ft.Colors.with_opacity(
                0.1,
                foreground_color(page),
            ),
        )
    ]

    angle = 0.0
    for _, count, color in segments:
        ratio = count / total
        ring = ft.ProgressRing(
            value=0,
            width=RING_SIZE,
            height=RING_SIZE,
            stroke_width=RING_STROKE,
            color=color,
            bgcolor=ft.Colors.TRANSPARENT,
            stroke_cap=ft.StrokeCap.BUTT,
            rotate=ft.Rotate(
                angle=angle,
                alignment=ft.Alignment.CENTER,
            ),
        )
        rings.append((ring, ratio))
        controls.append(ring)
        angle += ratio * 2 * math.pi

    return ft.Stack(
        width=RING_SIZE,
        height=RING_SIZE,
        alignment=ft.Alignment.CENTER,
        controls=controls,
    )


def _single_ring(
    page: ft.Page,
    *,
    ratio: float,
    color: str,
    rings: list[tuple[ft.ProgressRing, float]],
) -> ft.Control:
    ring = ft.ProgressRing(
        value=0,
        width=RING_SIZE,
        height=RING_SIZE,
        stroke_width=RING_STROKE,
        color=color,
        bgcolor=ft.Colors.with_opacity(0.14, color),
        stroke_cap=ft.StrokeCap.BUTT,
    )
    rings.append((ring, ratio))
    return ft.Stack(
        width=RING_SIZE,
        height=RING_SIZE,
        alignment=ft.Alignment.CENTER,
        controls=[ring],
    )


def _legend_row(
    page: ft.Page,
    *,
    color: str,
    label: str,
    count: int,
    compact: bool,
) -> ft.Row:
    size = 10 if compact else 12
    dot = 6 if compact else 8
    spacing = 4 if compact else 6
    return ft.Row(
        spacing=spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=dot,
                height=dot,
                border_radius=dot / 2,
                bgcolor=color,
            ),
            ui_text(
                label,
                size=size,
                color=ft.Colors.with_opacity(
                    0.82,
                    foreground_color(page),
                ),
            ),
            ui_text(
                str(count),
                size=size,
                weight=ft.FontWeight.BOLD,
                color=color,
            ),
        ],
    )


def _legend_panel(
    page: ft.Page,
    *,
    title: str,
    rows: list[tuple[str, int, str]],
    accent: str,
    compact: bool,
) -> ft.Container:
    width = COMPACT_PANEL_WIDTH if compact else PANEL_WIDTH
    return ft.Container(
        width=width,
        height=_panel_size(len(rows), compact)[1],
        padding=(
            ft.Padding.symmetric(horizontal=8, vertical=6)
            if compact
            else ft.Padding.symmetric(horizontal=10, vertical=8)
        ),
        border_radius=10 if compact else 12,
        bgcolor=background_color(page),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.28, accent),
        ),
        shadow=ft.BoxShadow(
            blur_radius=12 if compact else 14,
            color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
            offset=ft.Offset(2, 4),
        ),
        content=ft.Column(
            spacing=2 if compact else 3,
            controls=[
                ui_text(
                    title,
                    size=10 if compact else 12,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.with_opacity(
                        0.9,
                        foreground_color(page),
                    ),
                ),
                *[
                    _legend_row(
                        page,
                        color=color,
                        label=label,
                        count=count,
                        compact=compact,
                    )
                    for label, count, color in rows
                ],
            ],
        ),
    )


def _panel_size(rows: int, compact: bool) -> tuple[int, int]:
    if compact:
        return COMPACT_PANEL_WIDTH, 30 + 18 * rows
    return PANEL_WIDTH, 38 + 22 * rows


def _back_view(
    page: ft.Page,
    *,
    route: str,
    title: str,
    controls: list[ft.Control],
    rebuild: Callable[[], ft.View] | None = None,
    before: Callable[[], None] | None = None,
) -> ft.View:
    view = make_view(
        page,
        route=route,
        title=title,
        controls=controls,
        rebuild=rebuild,
        before=before,
        back=True,
        scroll=False,
    )
    if len(controls) == 1:
        column = controls[0]
        if getattr(column, "scroll", None) is not None:
            scroll_memory.remember(page, route, "page", column)
    scroll_memory.schedule_restore(page, view)
    return view


def _no_records_note(
    page: ft.Page,
    *,
    height: float,
    width: float | None = None,
) -> ft.Container:
    return no_records_note(page, height=height, width=width)


def _is_desktop_platform(page: ft.Page) -> bool:
    return is_desktop(page)


def _chart_viewport(
    content: ft.Control,
    *,
    height: float,
    width: float,
) -> ft.Row:
    # 视口被限制在图表宽度内，因此宽窗口会显示
    # 完整的左对齐图表，而不是拉伸柱形。
    return ft.Row(
        width=width,
        height=height + 16,
        vertical_alignment=ft.CrossAxisAlignment.START,
        scroll=ft.Scrollbar(
            orientation=ft.ScrollbarOrientation.BOTTOM,
            thumb_visibility=True,
            track_visibility=True,
        ),
        controls=[content],
    )


def _open_statistics_page(
    page: ft.Page,
    builder: Callable[[ft.Page], ft.View],
) -> None:
    view = builder(page)
    if page.views and getattr(page.views[-1], "route", "") == view.route:
        return
    push_view(page, view)


