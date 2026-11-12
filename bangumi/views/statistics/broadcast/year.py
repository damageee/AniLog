"""年份统计页。"""

from __future__ import annotations

import asyncio
import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui import scroll_memory
from bangumi.ui.anim import wait_until_ready
from bangumi.ui.anim import (
    animation,
    entry_animations_enabled,
)
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.ui.layout import (
    vertical_page,
)
from bangumi.data.statistics.models import BroadcastData
from bangumi.data.statistics.broadcast import broadcast_data
from bangumi.data.sorting import sort_detail_items
from bangumi.data.statistics.records import _record_item
from bangumi.views.templates.list_page import open_list_page
from bangumi.views.statistics.common.overlays import (
    _OverlayLayers,
    _install_overlay_hook,
    _overlay_placement,
    _register_overlay,
)
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    CHART_BAR_WIDTH,
    CHART_HEIGHT,
    CHART_MAX_BAR,
    CHART_SLOT,
    _accent,
    _chart_viewport,
    _back_view,
    _is_desktop_platform,
    _no_records_note,
)
from bangumi.ui.constants import (
    HOVER_SCALE_YEAR,
)


def _open_year_list(
    page: ft.Page,
    data: BroadcastData,
    year: int,
) -> None:
    rows = data.by_year.get(year, [])
    open_list_page(
        page,
        title=f"{year}年",
        route=f"/statistics/broadcast/year/{year}",
        entries=sort_detail_items(
            [_record_item(record) for record in rows]
        ),
        records=data.records,
    )


def year_view(page: ft.Page, *, animate_bars: bool = True) -> ft.View:
    route = "/statistics/broadcast/year"
    animate = (
        animate_bars
        and entry_animations_enabled()
        and first_entry(page, route)
    )
    if animate:
        mark_seen(page, route)
    data = broadcast_data()
    accent = _accent(page, "#2563EB", "#60A5FA")
    fg = foreground_color(page)
    desktop = _is_desktop_platform(page)
    overlay = _OverlayLayers(page)
    _register_overlay(page, overlay)
    _install_overlay_hook(page)

    counts = [len(data.by_year[year]) for year in data.years]
    max_count = max(counts, default=0) or 1
    total = sum(counts)
    chart_width = max(1, len(data.years)) * CHART_SLOT
    viewport_width = min(
        max(120.0, float(page.width or 1000) - 48),
        chart_width,
    )
    viewport_state: dict[str, float | None] = {
        "width": viewport_width,
    }

    label_text = ui_text("", size=12, color=fg)
    label = ft.Container(
        width=170,
        height=34,
        alignment=ft.Alignment.CENTER,
        ignore_interactions=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=8,
        bgcolor=background_color(page),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.25, accent),
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(2, 4),
        ),
        content=label_text,
    )

    active_year: dict[str, int | None] = {"year": None}

    def show_label(event: ft.ControlEvent, year: int, count: int) -> None:
        if view not in page.views or page.views[-1] is not view:
            return
        pos = _overlay_placement(page, event, width=170, height=34)
        active_year["year"] = year
        label_text.value = f"{year} · {count} 部"
        label.left = pos["left"]
        label.top = pos.get("top")
        label.bottom = pos.get("bottom")
        overlay.show(label)

    def hide_label(event: ft.ControlEvent, year: int) -> None:
        if active_year["year"] != year:
            return
        active_year["year"] = None
        overlay.remove(label)

    def open_year(event: ft.ControlEvent, year: int) -> None:
        _open_year_list(page, data, year)

    def set_hover_scale(event: ft.ControlEvent, value: float) -> None:
        control = getattr(event, "control", None)
        if control is None:
            return
        control.scale = ft.Scale(value)
        control.update()

    def enter_year(
        event: ft.ControlEvent,
        year: int,
        count: int,
    ) -> None:
        if not desktop:
            return
        control = getattr(event, "control", None)
        if control is None:
            return
        show_label(event, year, count)
        set_hover_scale(event, HOVER_SCALE_YEAR)

    def exit_year(event: ft.ControlEvent, year: int) -> None:
        if not desktop:
            return
        hide_label(event, year)
        set_hover_scale(event, 1.0)

    long_year: dict[str, int | None] = {"year": None}
    active_long_bar: dict[str, ft.Container | None] = {"bar": None}

    def scale_long(target: ft.Container | None, on: bool) -> None:
        if target is None:
            return
        target.scale = ft.Scale(HOVER_SCALE_YEAR if on else 1.0)
        try:
            target.update()
        except Exception:
            pass

    def long_start(
        event: ft.ControlEvent,
        year: int,
        count: int,
    ) -> None:
        long_year["year"] = year
        show_label(event, year, count)
        try:
            index = data.years.index(year)
        except ValueError:
            return
        current = active_long_bar["bar"]
        if current is not None:
            scale_long(current, False)
        target = bar_entries[index][0]
        scale_long(target, True)
        active_long_bar["bar"] = target

    def long_move(
        event: ft.ControlEvent,
        year: int,
    ) -> None:
        offset = getattr(event, "local_offset_from_origin", None)
        if offset is None:
            offset = getattr(event, "offset_from_origin", None)
        if offset is None:
            return
        try:
            index = data.years.index(year)
        except ValueError:
            return
        dx = float(getattr(offset, "x", 0) or 0)
        delta = int(round(dx / CHART_BAR_WIDTH))
        target_index = max(
            0,
            min(len(data.years) - 1, index + delta),
        )
        target_year = data.years[target_index]
        long_year["year"] = target_year
        show_label(event, target_year, counts[target_index])
        current = active_long_bar["bar"]
        if current is not None:
            scale_long(current, False)
        target = bar_entries[target_index][0]
        scale_long(target, True)
        active_long_bar["bar"] = target

    def long_end(
        event: ft.ControlEvent,
        year: int,
    ) -> None:
        hide_label(event, long_year["year"] or year)
        current = active_long_bar["bar"]
        if current is not None:
            scale_long(current, False)
        active_long_bar["bar"] = None
        long_year["year"] = None

    bars: list[ft.Control] = []
    bar_entries: list[tuple[ft.Container, ft.Text, int, int]] = []
    for index, year in enumerate(data.years):
        count = counts[index]
        target_height = round(count / max_count * CHART_MAX_BAR)
        bar = ft.Container(
            width=CHART_BAR_WIDTH,
            height=target_height if not animate else 0,
            border_radius=4,
            bgcolor=accent,
            animate=(
                animation(int(ANIMATION_SECONDS * 1000))
                if animate
                else None
            ),
        )
        bar.animate_scale = animation(
            150,
            ft.AnimationCurve.EASE_OUT,
        )
        bar.scale = ft.Scale(1.0)
        count_text = ui_text(
            str(count) if not animate else "0",
            size=9,
            color=accent,
            no_wrap=True,
        )
        year_label = ui_text(
            str(year),
            size=9,
            color=ft.Colors.with_opacity(0.68, fg),
            no_wrap=True,
        )
        column = ft.Column(
            width=CHART_SLOT,
            height=CHART_HEIGHT,
            spacing=1,
            alignment=ft.MainAxisAlignment.END,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[count_text, bar, year_label],
        )
        gesture = ft.GestureDetector(
            scale=ft.Scale(1.0),
            animate_scale=animation(
                150,
                ft.AnimationCurve.EASE_OUT,
            ),
            on_enter=(
                lambda event, y=year, c=count: enter_year(
                    event,
                    y,
                    c,
                )
            ),
            on_exit=(
                lambda event, y=year: exit_year(event, y)
            ),
            on_tap=(
                lambda event, y=year: open_year(event, y)
            ),
            on_long_press_start=(
                lambda event, y=year, c=count: long_start(
                    event,
                    y,
                    c,
                )
            ),
            on_long_press_move_update=(
                lambda event, y=year: long_move(event, y)
            ),
            on_long_press_end=(
                lambda event, y=year: long_end(event, y)
            ),
            on_long_press_cancel=(
                lambda event, y=year: long_end(event, y)
            ),
            content=column,
        )
        bars.append(gesture)
        bar_entries.append(
            (bar, count_text, count, target_height)
        )

    bars_row = ft.Row(
        width=chart_width,
        height=CHART_HEIGHT,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.END,
        controls=bars,
    )

    chart_scroll = _chart_viewport(
        bars_row,
        height=CHART_HEIGHT,
        width=viewport_width,
    )

    def on_frame_size(event) -> None:
        width = min(
            max(120.0, float(event.width or 0)),
            chart_width,
        )
        if width <= 0:
            return
        previous = viewport_state["width"]
        viewport_state["width"] = width
        if chart_scroll.width != width:
            chart_scroll.width = width
            chart_scroll.update()
        if (
            width < chart_width
            and (previous is None or width < previous)
        ):
            page.run_task(scroll_to_latest)

    chart_frame = ft.Row(
        on_size_change=on_frame_size,
        controls=[chart_scroll],
    )

    if data.years:
        page_controls: list[ft.Control] = [
            ui_text(
                f"{data.years[0]}–{data.years[-1]} · 共 {total} 部",
                size=12,
                color=ft.Colors.with_opacity(0.72, fg),
            ),
            chart_frame,
        ]
    else:
        page_controls = [
            _no_records_note(
                page,
                height=60,
                width=max(200.0, float(page.width or 1000) - 48),
            ),
        ]

    page_col = vertical_page(
        page_controls,
        spacing=10,
    )
    view = _back_view(
        page,
        route="/statistics/broadcast/year",
        rebuild=lambda: year_view(page, animate_bars=False),
        title="年份",
        controls=[page_col],
    )
    scroll_memory.remember(
        page, "/statistics/broadcast/year", "page", page_col
    )
    scroll_memory.remember(
        page, "/statistics/broadcast/year", "chart", chart_scroll
    )

    async def scroll_to_latest() -> None:
        await asyncio.sleep(0.1)
        if view not in page.views:
            return
        if getattr(chart_scroll, "page", None) is None:
            return
        try:
            await chart_scroll.scroll_to(offset=-1)
        except Exception:
            pass

    async def animate() -> None:
        if not await wait_until_ready(page, bars_row):
            return
        for bar, text, target, target_height in bar_entries:
            bar.height = target_height
            text.value = str(target)
        controls = [
            control
            for bar, text, _, _ in bar_entries
            for control in (bar, text)
        ]
        try:
            page.update(*controls)
        except RuntimeError:
            return
        except Exception:
            pass

    if data.years:
        if animate:
            page.run_task(animate)
        page.run_task(scroll_to_latest)
    return view


