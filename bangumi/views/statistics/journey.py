"""旅途（补完曲线/日历）页。"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
import random
import flet as ft
import flet.canvas as fcanvas
from bangumi.views.statistics.rating.charts import smooth_path_elements
from bangumi.ui.text_metrics import (
    text_width,
)
from bangumi.ui import scroll_memory
from bangumi.ui.heat_zoom import attach_heat_zoom, reset_heat_zoom
from bangumi.ui.anim import wait_until_ready
from bangumi.ui.anim import (
    animation,
    entry_animations_enabled,
)
from bangumi.ui.interaction import is_attached
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.views.navigation import (
    push_view,
)
from bangumi.ui.layout import (
    vertical_page,
)
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.data.statistics.models import (
    CompletionPoint,
    JourneyData,
)
from bangumi.data.statistics.records import _record_item
from bangumi.data.statistics.journey import journey_data
from bangumi.data.sorting import sort_detail_items
from bangumi.views.templates.list_page import (
    build_list_view,
    open_list_page,
)
from bangumi.views.statistics.common.overlays import (
    _OverlayLayers,
    _hide_page_overlay,
    _install_overlay_hook,
    _overlay_placement,
    _register_overlay,
)
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    ANIMATION_STEPS,
    CAL_CELL,
    CAL_GAP,
    CAL_WEEKDAY_WIDTH,
    JOURNEY_BASELINE,
    JOURNEY_HEIGHT,
    JOURNEY_TOP,
    _accent,
    _back_view,
    _is_desktop_platform,
)


_EMPTY_MONTH_MESSAGE = "你呀，真是怠惰呢！"


_EMPTY_MONTH_COLOR = "#166534"


_EMPTY_MONTH_SIZE = 30


def _open_month_list(
    page: ft.Page,
    data: JourneyData,
    key: tuple[int, int],
) -> None:
    """打开某个月的补完列表，或其空状态页面。"""
    month_points = [
        point
        for point in data.points
        if (point.date.year, point.date.month) == key
    ]
    title = f"{key[0]}.{key[1]:02d} 补完"
    route = f"/statistics/journey/month/{key[0]}-{key[1]:02d}"
    if month_points:
        _hide_page_overlay(page)

        def rebuild_month() -> ft.View:
            fresh = journey_data()
            fresh_points = [
                point
                for point in fresh.points
                if (point.date.year, point.date.month) == key
            ]
            return build_list_view(
                page,
                title=title,
                route=route,
                entries=sort_detail_items(
                    [
                        _record_item(point.record)
                        for point in fresh_points
                    ]
                ),
                records=fresh.records,
                before=lambda: _hide_page_overlay(page),
            )

        open_list_page(
            page,
            title=title,
            route=route,
            entries=sort_detail_items(
                [
                    _record_item(point.record)
                    for point in month_points
                ]
            ),
            records=data.records,
            before=lambda: _hide_page_overlay(page),
            rebuild=rebuild_month,
        )
        return
    _hide_page_overlay(page)
    if page.views and getattr(page.views[-1], "route", "") == route:
        return

    def build_empty() -> ft.View:
        return _back_view(
            page,
            route=route,
            title=title,
            rebuild=build_empty,
            controls=[
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        _EMPTY_MONTH_MESSAGE,
                        size=_EMPTY_MONTH_SIZE,
                        color=_EMPTY_MONTH_COLOR,
                        weight=ft.FontWeight.BOLD,
                    ),
                )
            ],
        )

    push_view(page, build_empty())


def open_month_completion(
    page: ft.Page,
    year: int,
    month: int,
) -> None:
    """Open the completion list for a month (used by the 已阅 table)."""
    _open_month_list(page, journey_data(), (year, month))


def _journey_shapes(
    *,
    months: list[tuple[int, int]],
    month_entries: dict[tuple[int, int], int],
    month_episodes: dict[tuple[int, int], int],
    revealed: int,
    show_entries: bool,
    show_episodes: bool,
    slot: float,
    entries_color: str,
    episodes_color: str,
    cumulative: bool = False,
) -> list[fcanvas.Shape]:
    monthly_entries = [month_entries[key] for key in months]
    monthly_episodes = [month_episodes[key] for key in months]

    shown = min(revealed, len(months))
    if shown <= 0:
        return []

    if cumulative:
        total_entries = sum(monthly_entries) or 1
        total_episodes = sum(monthly_episodes) or 1
        entry_values: list[float] = []
        episode_values: list[float] = []
        running_entries = 0
        running_episodes = 0
        for index in range(len(monthly_entries)):
            running_entries += monthly_entries[index]
            running_episodes += monthly_episodes[index]
            entry_values.append(running_entries / total_entries)
            episode_values.append(running_episodes / total_episodes)
        max_y = 1.0
    else:
        entry_values = list(monthly_entries)
        episode_values = list(monthly_episodes)
        max_y = max(
            max(monthly_entries, default=0) if show_entries else 0,
            max(monthly_episodes, default=0) if show_episodes else 0,
            1,
        )

    curve_elements = smooth_path_elements

    def series(values, color: str) -> list[fcanvas.Shape]:
        points = [
            (
                index * slot + slot / 2,
                JOURNEY_BASELINE
                - values[index]
                / max_y
                * (JOURNEY_BASELINE - JOURNEY_TOP),
            )
            for index in range(shown)
        ]
        if len(points) < 2:
            return []
        area_elements: list[fcanvas.Path.PathElement] = [
            fcanvas.Path.MoveTo(points[0][0], JOURNEY_BASELINE),
            fcanvas.Path.LineTo(points[0][0], points[0][1]),
        ]
        area_elements.extend(curve_elements(points, move=False))
        area_elements.append(
            fcanvas.Path.LineTo(points[-1][0], JOURNEY_BASELINE)
        )
        area_elements.append(fcanvas.Path.Close())
        shapes: list[fcanvas.Shape] = [
            fcanvas.Path(
                elements=area_elements,
                paint=ft.Paint(
                    color=ft.Colors.with_opacity(0.08, color),
                    style=ft.PaintingStyle.FILL,
                ),
            ),
            fcanvas.Path(
                elements=curve_elements(points, move=True),
                paint=ft.Paint(
                    color=color,
                    stroke_width=2,
                    style=ft.PaintingStyle.STROKE,
                    stroke_cap=ft.StrokeCap.ROUND,
                ),
            ),
        ]
        return shapes

    shapes: list[fcanvas.Shape] = []
    if show_entries:
        shapes.extend(series(entry_values, entries_color))
    if show_episodes:
        shapes.extend(series(episode_values, episodes_color))
    return shapes


def journey_view(page: ft.Page) -> ft.View:
    route = "/statistics/journey"
    animate = entry_animations_enabled() and first_entry(page, route)
    prev_toggles: dict = {}
    if page.views:
        top = page.views[-1]
        if (
            str(getattr(top, "route", "")) == route
            and isinstance(getattr(top, "data", None), dict)
        ):
            prev_toggles = dict(top.data.get("chart_toggles") or {})
    data = journey_data()
    fg = foreground_color(page)
    entries_color = _accent(page, "#2563EB", "#60A5FA")
    episodes_color = _accent(page, "#F59E0B", "#FBBF24")
    desktop = _is_desktop_platform(page)
    overlay = _OverlayLayers(page)
    _register_overlay(page, overlay)
    _install_overlay_hook(page)

    if not data.points:
        return _back_view(
            page,
            route="/statistics/journey",
            rebuild=lambda: journey_view(page),
            title="旅途",
            controls=[
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        _EMPTY_MONTH_MESSAGE,
                        size=_EMPTY_MONTH_SIZE,
                        color=_EMPTY_MONTH_COLOR,
                        weight=ft.FontWeight.BOLD,
                    ),
                )
            ],
        )

    months = data.months
    month_index_by_key = {
        key: index for index, key in enumerate(months)
    }
    cum_entries: list[int] = []
    cum_episodes: list[int] = []
    running_entries = 0
    running_episodes = 0
    for key in months:
        running_entries += data.month_entries[key]
        running_episodes += data.month_episodes[key]
        cum_entries.append(running_entries)
        cum_episodes.append(running_episodes)
    default_width = max(360.0, 44.0 * len(months))
    page_width = fit_chart_width(page, default_width)
    chart_width = page_width
    slot = chart_width / len(months)
    chart_toggles = {
        "entries": bool(prev_toggles.get("entries", True)),
        "episodes": bool(prev_toggles.get("episodes", True)),
        "cumulative": bool(prev_toggles.get("cumulative", False)),
    }
    chart_state = {
        "entries": chart_toggles["entries"],
        "episodes": chart_toggles["episodes"],
        "cumulative": chart_toggles["cumulative"],
        "revealed": 0 if animate else len(months),
    }
    curve_anim = {"running": bool(animate)}

    curve_label_text = ui_text("", size=11, color=fg)
    curve_label = ft.Container(
        width=250,
        height=36,
        alignment=ft.Alignment.CENTER,
        ignore_interactions=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=8,
        bgcolor=background_color(page),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.25, entries_color),
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(2, 4),
        ),
        content=curve_label_text,
    )
    active_month: dict[str, tuple[int, int] | None] = {"key": None}

    def show_month(
        event: ft.ControlEvent,
        key: tuple[int, int],
    ) -> None:
        if not page_alive():
            return
        if chart_state["cumulative"]:
            index = month_index_by_key[key]
            text = (
                f"{key[0]}.{key[1]:02d} · "
                f"累计 {cum_entries[index]} 部 / "
                f"{cum_episodes[index]} 集"
            )
        else:
            text = (
                f"{key[0]}.{key[1]:02d} · "
                f"新增 {data.month_entries[key]} 部 / "
                f"{data.month_episodes[key]} 集"
            )
        width = max(
            140,
            min(300, text_width(text, size=11) + 28),
        )
        curve_label.width = width
        pos = _overlay_placement(
            page,
            event,
            width=width,
            height=36,
        )
        active_month["key"] = key
        active_day["day"] = None
        overlay.remove(day_label)
        curve_label_text.value = text
        curve_label.left = pos["left"]
        curve_label.top = pos.get("top")
        curve_label.bottom = pos.get("bottom")
        overlay.show(curve_label)

    def hide_month(
        event: ft.ControlEvent,
        key: tuple[int, int],
    ) -> None:
        if active_month["key"] != key:
            return
        active_month["key"] = None
        overlay.remove(curve_label)

    def hide_curve_label() -> None:
        active_month["key"] = None
        overlay.remove(curve_label)

    canvas = fcanvas.Canvas(
        width=chart_width,
        height=JOURNEY_HEIGHT,
        shapes=[],
    )

    def redraw_curve() -> None:
        canvas.shapes = _journey_shapes(
            months=months,
            month_entries=data.month_entries,
            month_episodes=data.month_episodes,
            revealed=chart_state["revealed"],
            show_entries=chart_state["entries"],
            show_episodes=chart_state["episodes"],
            slot=slot,
            entries_color=entries_color,
            episodes_color=episodes_color,
            cumulative=chart_state["cumulative"],
        )

    def month_at(event: ft.ControlEvent) -> tuple[int, int]:
        pos = getattr(event, "local_position", None)
        x = float(pos.x) if pos is not None else 0.0
        index = int(x // slot) if slot > 0 else 0
        index = max(0, min(len(months) - 1, index))
        return months[index]

    def on_curve_hover(event: ft.ControlEvent) -> None:
        pos = getattr(event, "local_position", None)
        if pos is None:
            key = active_month["key"]
            if key is None:
                return
        else:
            key = month_at(event)
        show_month(event, key)

    curve_gesture = ft.GestureDetector(
        width=chart_width,
        height=JOURNEY_HEIGHT,
        on_enter=lambda event: show_month(event, month_at(event)),
        on_hover=on_curve_hover,
        on_long_press_start=(
            lambda event: show_month(event, month_at(event))
        ),
        on_long_press_move_update=(
            lambda event: show_month(event, month_at(event))
        ),
        on_long_press_end=lambda event: hide_curve_label(),
        on_long_press_cancel=lambda event: hide_curve_label(),
        on_exit=lambda event: hide_curve_label(),
        content=canvas,
    )

    chart_content = ft.Container(
        width=chart_width,
        height=JOURNEY_HEIGHT,
        content=curve_gesture,
    )

    def on_curve_frame(event) -> None:
        nonlocal chart_width, slot
        width = min(
            default_width,
            max(120.0, float(event.width or 0)),
        )
        if width <= 0:
            return
        chart_width = width
        slot = width / len(months)
        if not curve_anim["running"]:
            chart_state["revealed"] = len(months)
        redraw_curve()
        canvas.width = width
        curve_gesture.width = width
        chart_content.width = width
        try:
            canvas.update()
        except Exception:
            pass
        try:
            chart_content.update()
        except Exception:
            pass

    curve_frame = ft.Row(
        on_size_change=on_curve_frame,
        controls=[chart_content],
    )

    entries_check = ft.Checkbox(
        label="部数",
        value=chart_toggles["entries"],
        fill_color=entries_color,
    )
    episodes_check = ft.Checkbox(
        label="集数",
        value=chart_toggles["episodes"],
        fill_color=episodes_color,
    )
    cumulative_check = ft.Checkbox(
        label="累积",
        value=chart_toggles["cumulative"],
        fill_color=ft.Colors.PURPLE,
    )

    def on_toggle(event: ft.ControlEvent) -> None:
        chart_toggles["entries"] = bool(entries_check.value)
        chart_toggles["episodes"] = bool(episodes_check.value)
        chart_toggles["cumulative"] = bool(cumulative_check.value)
        chart_state["entries"] = chart_toggles["entries"]
        chart_state["episodes"] = chart_toggles["episodes"]
        chart_state["cumulative"] = chart_toggles["cumulative"]
        redraw_curve()
        canvas.update()

    entries_check.on_change = on_toggle
    episodes_check.on_change = on_toggle
    cumulative_check.on_change = on_toggle
    legend = ft.Row(
        spacing=18,
        controls=[entries_check, episodes_check, cumulative_check],
    )

    # 日历状态：仅保留确实有补完记录的年份。
    current_year = dt.date.today().year
    years = sorted(data.by_year)
    default_year = (
        current_year if current_year in years else years[-1]
    )
    summary_text = ui_text(
        "",
        size=11,
        color=fg,
    )
    year_text = ui_text(str(default_year), size=12, color=fg)
    year_button = ft.PopupMenuButton(
        content=ft.Container(
            width=88,
            height=30,
            padding=ft.Padding.symmetric(horizontal=8),
            border=ft.Border.all(
                1,
                ft.Colors.with_opacity(0.35, fg),
            ),
            border_radius=4,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                spacing=4,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    year_text,
                    ft.Icon(
                        ft.Icons.ARROW_DROP_DOWN,
                        size=16,
                        color=fg,
                    ),
                ],
            ),
        ),
        items=[
            ft.PopupMenuItem(
                content=ui_text(str(year), size=12),
                on_click=lambda event, y=year: select_year(y),
            )
            for year in years
        ],
    )
    calendar_holder = ft.Column(spacing=8)
    cells_to_fade: list[ft.Container] = []

    day_label = ft.Container(
        width=250,
        ignore_interactions=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        border_radius=8,
        bgcolor=background_color(page),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.25, entries_color),
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(2, 4),
        ),
        content=ft.Column(spacing=2),
    )
    active_day: dict[str, dt.date | None] = {"day": None}

    def show_day(
        event: ft.ControlEvent,
        day: dt.date,
        points: list[CompletionPoint],
    ) -> None:
        if view not in page.views or page.views[-1] is not view:
            return
        label_text = f"{day.strftime('%Y.%m.%d')}  {len(points)}部"
        width = max(
            96,
            text_width(label_text, size=11, bold=True) + 30,
        )
        height = 32
        day_label.content = ui_text(
            label_text,
            size=11,
            weight=ft.FontWeight.BOLD,
            no_wrap=True,
            overflow=ft.TextOverflow.VISIBLE,
            text_align=ft.TextAlign.CENTER,
        )
        day_label.alignment = ft.Alignment.CENTER
        day_label.width = width
        day_label.height = height
        pos = _overlay_placement(
            page,
            event,
            width=width,
            height=height,
        )
        active_day["day"] = day
        active_month["key"] = None
        overlay.remove(curve_label)
        day_label.left = pos["left"]
        day_label.top = pos.get("top")
        day_label.bottom = pos.get("bottom")
        overlay.show(day_label)

    def hide_day(
        event: ft.ControlEvent,
        day: dt.date,
    ) -> None:
        if active_day["day"] != day:
            return
        active_day["day"] = None
        overlay.remove(day_label)

    def hide_all_layers(
        event: ft.ControlEvent | None = None,
    ) -> None:
        active_month["key"] = None
        active_day["day"] = None
        overlay.hide()
        reset_heat_zoom(page)

    def open_day(
        event: ft.ControlEvent,
        day: dt.date,
        points: list[CompletionPoint],
    ) -> None:
        open_list_page(
            page,
            title=f"{day.strftime('%Y.%m.%d')} 补完",
            route=f"/statistics/journey/day/{day.isoformat()}",
            entries=sort_detail_items(
                [_record_item(point.record) for point in points]
            ),
            records=data.records,
            before=lambda: _hide_page_overlay(page),
        )

    def build_calendar(
        year: int,
        *,
        animate: bool = True,
    ) -> tuple[list[ft.Control], list[ft.Container]]:
        items = data.by_year.get(year, {})
        completed = sum(len(day_items) for day_items in items.values())
        episodes = sum(
            point.episodes
            for day_items in items.values()
            for point in day_items
        )
        summary_text.value = f"共 {completed} 部 {episodes} 集"

        first = dt.date(year, 1, 1)
        last = dt.date(year, 12, 31)
        start = first - dt.timedelta(days=first.weekday())
        end = last + dt.timedelta(days=6 - last.weekday())
        weeks = ((end - start).days // 7) + 1

        cal_active: dict[str, dt.date | None] = {"day": None}
        day_cells: dict[dt.date, ft.Container] = {}
        active_cell: dict[str, ft.Container | None] = {"cell": None}

        def scale_day(
            target: ft.Container | None,
            on: bool,
        ) -> None:
            if target is None:
                return
            target.scale = ft.Scale(1.2 if on else 1.0)
            try:
                target.update()
            except Exception:
                pass

        def cal_show(
            event: ft.ControlEvent,
            day: dt.date,
            points: list[CompletionPoint],
        ) -> None:
            current = active_cell["cell"]
            if current is not None:
                scale_day(current, False)
            target = day_cells.get(day)
            scale_day(target, True)
            active_cell["cell"] = target
            cal_active["day"] = day
            show_day(event, day, points)

        def cal_move(
            event: ft.ControlEvent,
            day: dt.date,
        ) -> None:
            offset = getattr(event, "local_offset_from_origin", None)
            if offset is None:
                offset = getattr(event, "offset_from_origin", None)
            if offset is None:
                return
            dx = float(getattr(offset, "x", 0) or 0)
            dy = float(getattr(offset, "y", 0) or 0)
            step = CAL_CELL + CAL_GAP
            week_delta = int(round(dx / step)) if step else 0
            weekday_delta = int(round(dy / step)) if step else 0
            target = day + dt.timedelta(
                days=week_delta * 7 + weekday_delta
            )
            if target < first or target > last:
                return
            target_points = items.get(target, [])
            if target_points:
                current = active_cell["cell"]
                if current is not None:
                    scale_day(current, False)
                target_cell = day_cells.get(target)
                scale_day(target_cell, True)
                active_cell["cell"] = target_cell
                cal_active["day"] = target
                show_day(event, target, target_points)
            else:
                current_day = cal_active["day"] or day
                hide_day(event, current_day)

        def cal_end(
            event: ft.ControlEvent,
            day: dt.date,
        ) -> None:
            current = cal_active["day"] or day
            hide_day(event, current)
            current_cell = active_cell["cell"]
            if current_cell is not None:
                scale_day(current_cell, False)
            active_cell["cell"] = None
            cal_active["day"] = None

        month_labels = [""] * weeks
        for month in range(1, 13):
            day = dt.date(year, month, 1)
            index = (day - start).days // 7
            if not month_labels[index]:
                month_labels[index] = str(month)

        label_row = ft.Row(
            spacing=CAL_GAP,
            controls=[
                ft.Container(width=CAL_WEEKDAY_WIDTH),
                *[
                    ft.Container(
                        width=CAL_CELL,
                        height=10,
                        alignment=ft.Alignment.CENTER,
                        content=ui_text(
                            label,
                            size=7,
                            color=ft.Colors.with_opacity(0.7, fg),
                            no_wrap=True,
                        ),
                    )
                    for label in month_labels
                ],
            ],
        )

        max_day = max(
            (len(day_items) for day_items in items.values()),
            default=0,
        )
        fade_cells: list[ft.Container] = []
        week_columns: list[ft.Control] = []
        for week in range(weeks):
            column_cells: list[ft.Control] = []
            for weekday in range(7):
                day = start + dt.timedelta(
                    days=week * 7 + weekday
                )
                if day < first or day > last:
                    column_cells.append(
                        ft.Container(
                            width=CAL_CELL,
                            height=CAL_CELL,
                        )
                    )
                    continue
                points = items.get(day, [])
                ratio = (
                    len(points) / max_day if max_day else 0.0
                )
                if points:
                    bgcolor = ft.Colors.with_opacity(
                        0.18 + 0.72 * ratio,
                        entries_color,
                    )
                else:
                    bgcolor = None
                cell = ft.Container(
                    width=CAL_CELL,
                    height=CAL_CELL,
                    border_radius=2,
                    bgcolor=bgcolor,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.08, fg),
                    ),
                    opacity=0 if animate else 1,
                    scale=ft.Scale(1.4 if animate else 1.0),
                    animate_scale=(
                        animation(220)
                        if animate
                        else None
                    ),
                    animate_opacity=(
                        animation(280)
                        if animate
                        else None
                    ),
                )
                attach_heat_zoom(
                    page,
                    cell,
                    initial_scale=1.4 if animate else 1.0,
                )
                day_cells[day] = cell
                fade_cells.append(cell)
                if points:
                    gesture = ft.GestureDetector(
                        width=CAL_CELL,
                        height=CAL_CELL,
                        on_enter=(
                            lambda event, d=day, p=points: show_day(
                                event,
                                d,
                                p,
                            )
                        ),
                        on_exit=(
                            lambda event, d=day: hide_day(
                                event,
                                d,
                            )
                        ),
                        on_tap=(
                            lambda event, d=day, p=points: (
                                open_day(event, d, p)
                            )
                        ),
                        on_long_press_start=(
                            lambda event, d=day, p=points: cal_show(
                                event,
                                d,
                                p,
                            )
                        ),
                        on_long_press_move_update=(
                            lambda event, d=day: cal_move(event, d)
                        ),
                        on_long_press_end=(
                            lambda event, d=day: cal_end(event, d)
                        ),
                        on_long_press_cancel=(
                            lambda event, d=day: cal_end(event, d)
                        ),
                        content=cell,
                    )
                    column_cells.append(gesture)
                else:
                    column_cells.append(cell)
            week_columns.append(
                ft.Column(
                    spacing=CAL_GAP,
                    controls=column_cells,
                )
            )

        weekday_labels = ("一", "", "三", "", "五", "", "")
        weekday_column = ft.Column(
            spacing=CAL_GAP,
            controls=[
                ft.Container(
                    width=CAL_WEEKDAY_WIDTH,
                    height=CAL_CELL,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        weekday_labels[index],
                        size=8,
                        color=ft.Colors.with_opacity(0.7, fg),
                    ),
                )
                for index in range(7)
            ],
        )
        grid = ft.Row(
            spacing=CAL_GAP,
            controls=[weekday_column, *week_columns],
        )
        grid_width = (
            CAL_WEEKDAY_WIDTH
            + CAL_GAP
            + weeks * CAL_CELL
            + (weeks - 1) * CAL_GAP
        )
        grid_content = ft.Column(
            width=grid_width,
            spacing=4,
            controls=[label_row, grid],
        )
        grid_scroll = ft.Row(
            scroll=ft.Scrollbar(
                orientation=ft.ScrollbarOrientation.BOTTOM,
                thumb_visibility=True,
                track_visibility=True,
            ),
            controls=[grid_content],
        )
        scroll_memory.remember(
            page,
            "/statistics/journey",
            "calendar",
            grid_scroll,
        )
        scale_legend = ft.Row(
            alignment=ft.MainAxisAlignment.START,
            spacing=3,
            controls=[
                ui_text("Less", size=9, color=fg),
                *[
                    ft.Container(
                        width=CAL_CELL,
                        height=CAL_CELL,
                        border_radius=2,
                        bgcolor=ft.Colors.with_opacity(
                            opacity,
                            entries_color,
                        ),
                    )
                    for opacity in (0.18, 0.35, 0.52, 0.69, 0.86)
                ],
                ui_text("More", size=9, color=fg),
            ],
        )
        return [grid_scroll, scale_legend], fade_cells

    initial_controls, initial_cells = build_calendar(
        default_year,
        animate=animate,
    )
    calendar_holder.controls = initial_controls

    def select_year(year: int) -> None:
        overlay.hide()
        controls, cells = build_calendar(year, animate=True)
        calendar_holder.controls = controls
        year_text.value = str(year)
        year_button.update()
        page.run_task(animate_cells, cells)
        page.update(calendar_holder)

    async def animate_cells(cells: list[ft.Container]) -> None:
        if not cells:
            return
        if not await wait_until_ready(page, cells[0]):
            return
        if not (
            page.views
            and str(getattr(page.views[-1], "route", "")) == route
        ):
            return
        mark_seen(page, route)
        random.shuffle(cells)
        total = len(cells)
        batches = 24
        size = max(1, math.ceil(total / batches))
        for start in range(0, total, size):
            if not page_alive():
                return
            batch = cells[start : start + size]
            for cell in batch:
                cell.opacity = 1
                cell.scale = ft.Scale(1.0)
            try:
                page.update(*batch)
            except RuntimeError:
                return
            except Exception:
                pass
            await asyncio.sleep(ANIMATION_SECONDS / batches)

    page_col = vertical_page(
        [
            ui_text(
                "补完曲线",
                size=15,
                weight=ft.FontWeight.BOLD,
                color=fg,
            ),
            curve_frame,
            legend,
            ft.Container(height=6),
            ft.Row(
                spacing=10,
                vertical_alignment=(
                    ft.CrossAxisAlignment.CENTER
                ),
                controls=[
                    ui_text(
                        "活跃度",
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color=fg,
                    ),
                    year_button,
                    summary_text,
                ],
            ),
            calendar_holder,
        ],
        spacing=10,
    )
    view = _back_view(
        page,
        route="/statistics/journey",
        title="旅途",
        rebuild=lambda: journey_view(page),
        before=hide_all_layers,
        controls=[
            ft.GestureDetector(
                expand=True,
                on_tap=hide_all_layers,
                content=page_col,
            )
        ],
    )
    scroll_memory.remember(
        page, "/statistics/journey", "page", page_col
    )

    def page_alive() -> bool:
        return any(
            getattr(v, "route", "") == "/statistics/journey"
            for v in page.views
        )

    async def animate_curve() -> None:
        if not (
            page.views
            and str(getattr(page.views[-1], "route", "")) == route
        ):
            curve_anim["running"] = False
            return
        if not await wait_until_ready(page, canvas):
            if not await wait_until_ready(page, canvas):
                curve_anim["running"] = False
                return
        if not (
            page.views
            and str(getattr(page.views[-1], "route", "")) == route
            and is_attached(canvas)
        ):
            curve_anim["running"] = False
            return
        mark_seen(page, route)
        steps = ANIMATION_STEPS
        for step in range(1, steps + 1):
            if not (
                page.views
                and str(getattr(page.views[-1], "route", "")) == route
            ):
                curve_anim["running"] = False
                return
            eased = 1 - (1 - step / steps) ** 3
            chart_state["revealed"] = max(
                1,
                int(round(eased * len(months))),
            )
            redraw_curve()
            try:
                canvas.update()
            except RuntimeError:
                curve_anim["running"] = False
                return
            except Exception:
                pass
            await asyncio.sleep(ANIMATION_SECONDS / steps)
        curve_anim["running"] = False
        chart_state["revealed"] = len(months)
        redraw_curve()
        try:
            canvas.update()
        except RuntimeError:
            return
        except Exception:
            pass

    redraw_curve()
    view_data = view.data if isinstance(view.data, dict) else {}
    view_data["chart_toggles"] = chart_toggles
    view.data = view_data
    if animate:
        page.run_task(animate_curve)
        page.run_task(animate_cells, initial_cells)
    return view


