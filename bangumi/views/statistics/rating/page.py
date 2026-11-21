"""评分统计与评分榜单页。"""

from __future__ import annotations

import asyncio
import statistics as stats_lib
from collections import (
    Counter,
)
import flet as ft
from bangumi.core.utils import format_number
import flet.canvas as fcanvas
from bangumi.ui.text_metrics import (
    text_width,
)
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.platform import is_mobile, is_wide
from bangumi.ui.heat_zoom import animate_heat_cells, attach_heat_zoom
from bangumi.ui.anim import wait_until_ready
from bangumi.ui.anim import (
    animation,
    entry_animations_enabled,
)
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.ui.anim import animation
from bangumi.ui.constants import (
    ANIM_BASE_MS,
    HOVER_SCALE_BAR,
)
from bangumi.ui.events import is_hover
from bangumi.ui.interaction import FloatingLabel
from bangumi.views.widgets.stat_card import stat_card
from bangumi.ui.layout import (
    vertical_page,
)
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.data.quarter_core import (
    broadcast_dates,
    earliest_broadcast_date,
    quarter_for_month,
    quarter_label,
)
from bangumi.data.watched_data import (
    Record,
    load_records,
)
from bangumi.data.statistics.constants import (
    SEASONS,
)
from bangumi.data.statistics.journey import _completion_date
from bangumi.views.general.detail_completion import (
    open_completion_month,
)
from bangumi.views.general.detail_quarter_works import (
    build_quarter_works_view,
)
from bangumi.views.navigation import push_view
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    ANIMATION_STEPS,
    JOURNEY_BASELINE,
    JOURNEY_HEIGHT,
    JOURNEY_TOP,
    _accent,
    _back_view,
    range_label,
)


from . import charts
from .data import (
    cumulative_series,
    monthly_series,
    quarterly_series,
)
from .rankings import open_rating_bars
from .works_range import _open_rating_range


def rating_view(page: ft.Page) -> ft.View:
    route = "/statistics/ratings"
    animate = entry_animations_enabled() and first_entry(page, route)
    prev_toggles: dict = {}
    if page.views:
        top = page.views[-1]
        if (
            str(getattr(top, "route", "")) == route
            and isinstance(getattr(top, "data", None), dict)
        ):
            prev_toggles = dict(top.data.get("chart_toggles") or {})
    chart_toggles = {
        "monthly": bool(prev_toggles.get("monthly", True)),
        "cumulative": bool(prev_toggles.get("cumulative", True)),
    }
    records = load_records()
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    accent = _accent(page, "#2563EB", "#60A5FA")
    monthly_color = accent
    cumulative_color = _accent(page, "#F59E0B", "#FBBF24")

    ratings: list[int] = []
    era_quarters: dict[tuple[int, int], list[int]] = {}
    taste_pairs: list[tuple[tuple[int, int, int], int]] = []
    for record in records:
        raw = str(record.get("rating") or "").strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if not 0 <= value <= 100:
            continue
        ratings.append(value)
        dates = broadcast_dates(str(record.get("broadcast") or ""))
        keys = {
            (date[0], quarter_for_month(date[1])[0])
            for date in dates
        }
        for key in keys:
            era_quarters.setdefault(key, []).append(value)
        completion = _completion_date(
            str(record.get("completion") or "")
        )
        if completion is not None:
            taste_pairs.append(
                (
                    (completion.year, completion.month, completion.day),
                    value,
                )
            )

    if not ratings:
        return _back_view(
            page,
            route="/statistics/ratings",
            rebuild=lambda: rating_view(page),
            title="评分",
            controls=[
                vertical_page(
                    [
                        ft.Container(
                            height=60,
                            alignment=ft.Alignment.CENTER,
                            content=ui_text(
                                "无评分数据",
                                size=18,
                                color=ft.Colors.with_opacity(0.45, fg),
                            ),
                        )
                    ]
                )
            ],
        )

    n = len(ratings)
    ordered = sorted(ratings)
    mean = float(stats_lib.fmean(ordered))
    median = float(stats_lib.median(ordered))
    mode_counts = Counter(ratings)
    mode_value, mode_count = max(
        mode_counts.items(),
        key=lambda item: (item[1], item[0]),
    )

    bins = [0] * 20
    for value in ratings:
        bins[min(19, value // 5)] += 1
    best_bin = max(
        range(20),
        key=lambda index: (bins[index], index),
    )
    best_bin_label = (
        "95–100"
        if best_bin == 19
        else f"{best_bin * 5}–{best_bin * 5 + 4}"
    )

    def card(
        title: str,
        value: str,
        *,
        expand: int | None = None,
    ) -> ft.Control:
        return stat_card(
            page,
            title,
            value,
            accent=accent,
            expand=expand,
        )

    row_specs: list[list[tuple[str, str]]] = [
        [
            ("数量", f"{n} 部"),
            ("平均分", format_number(mean)),
        ],
        [
            ("中位数", format_number(median)),
            ("众数", f"{mode_value}"),
        ],
        [
            ("最高分", str(ordered[-1])),
            ("最低分", str(ordered[0])),
        ],
        [
            (
                "最高频分段",
                f"{best_bin_label}（{bins[best_bin]} 部）",
            ),
        ],
    ]
    hist_width = fit_chart_width(page, 520.0, min_width=280.0)
    slot = hist_width / 20
    available = float(hist_width)

    def allocate(
        needs: list[float],
        width: float,
    ) -> list[float]:
        count = len(needs)
        fixed: dict[int, float] = {}
        while True:
            remaining = width - sum(fixed.values())
            free = [
                index
                for index in range(count)
                if index not in fixed
            ]
            if not free:
                break
            share = remaining / len(free)
            grown = next(
                (
                    index
                    for index in free
                    if needs[index] > share
                ),
                None,
            )
            if grown is None:
                for index in free:
                    fixed[index] = share
                break
            fixed[grown] = needs[grown]
        return [
            max(needs[index], fixed.get(index, 0.0))
            for index in range(count)
        ]

    card_rows: list[ft.Row] = []
    for spec in row_specs:
        if len(spec) == 1:
            card_rows.append(
                ft.Row(
                    spacing=12,
                    controls=[
                        card(spec[0][0], spec[0][1], expand=1)
                    ],
                )
            )
            continue
        needs = [
            text_width(title, size=13)
            + text_width(value, size=20, bold=True)
            + 40.0
            for title, value in spec
        ]
        widths = allocate(
            needs,
            available - 12 * (len(spec) - 1),
        )
        weights = [
            max(1, int(width * 100)) for width in widths
        ]
        card_rows.append(
            ft.Row(
                spacing=12,
                controls=[
                    card(title, value, expand=weight)
                    for (title, value), weight in zip(
                        spec, weights
                    )
                ],
            )
        )

    max_bin = max(bins) or 1
    bar_height = JOURNEY_BASELINE - JOURNEY_TOP
    hist_bars: list[tuple[ft.Container, float]] = []
    slot_bars: list[ft.Container | None] = []
    hist_label = FloatingLabel(page)
    active_hist: dict[str, ft.Container | None] = {"bar": None}

    def scale_hist(target: ft.Container | None, on: bool) -> None:
        if target is None:
            return
        target.scale = ft.Scale(HOVER_SCALE_BAR if on else 1.0)
        try:
            target.update()
        except Exception:
            pass

    def show_hist_label(event: ft.ControlEvent) -> None:
        pos = getattr(event, "local_position", None)
        x = float(pos.x) if pos is not None else 0.0
        index = max(0, min(19, int(x // slot))) if slot else 0
        start = index * 5
        end = 100 if index == 19 else start + 5
        count = bins[index]
        hist_label.show(
            event, f"{range_label(start, end)} · {count} 部"
        )
        current = active_hist["bar"]
        if current is not None:
            scale_hist(current, False)
        target = slot_bars[index] if index < len(slot_bars) else None
        scale_hist(target, True)
        active_hist["bar"] = target

    def end_hist(event: ft.ControlEvent) -> None:
        current = active_hist["bar"]
        if current is not None:
            scale_hist(current, False)
        active_hist["bar"] = None
        hist_label.hide()

    def histogram_bar(index: int) -> ft.Container:
        start = index * 5
        end = 100 if index == 19 else start + 5
        has_value = bins[index] > 0
        target = (
            max(1.0, bins[index] / max_bin * bar_height)
            if has_value
            else 0.0
        )
        bar = ft.Container(
            width=slot - 6,
            height=0 if animate else target,
            bgcolor=accent,
            border_radius=3,
            animate=(
                animation(int(ANIMATION_SECONDS * 1000))
                if animate
                else None
            ),
        )
        if has_value:
            hist_bars.append((bar, target))
            bar.scale = ft.Scale(1.0)
            bar.animate_scale = animation(
                ANIM_BASE_MS,
                ft.AnimationCurve.EASE_OUT,
            )

            def on_hover(
                event: ft.ControlEvent,
                target: ft.Container = bar,
            ) -> None:
                hovered = is_hover(event)
                target.scale = ft.Scale(
                    HOVER_SCALE_BAR if hovered else 1.0
                )
                target.update()

            # 命中高度取柱高；短于 1/4 完整高度时才扩大。
            hit_h = max(float(target), JOURNEY_HEIGHT / 4.0)
            hit_layer = ft.Container(
                width=slot - 6,
                height=hit_h,
                bgcolor=ft.Colors.TRANSPARENT,
                on_hover=on_hover,
                on_click=(
                    lambda event, s=start, e=end: _open_rating_range(
                        page, s, e
                    )
                ),
            )
            bar.bottom = 0.0
            slot_content = ft.Stack(
                width=slot - 6,
                height=hit_h,
                controls=[bar, hit_layer],
            )
        else:
            slot_content = ft.Container(width=slot - 6, height=0)

        slot_container = ft.Container(
            width=slot,
            height=JOURNEY_HEIGHT,
            alignment=ft.Alignment.BOTTOM_CENTER,
            tooltip=(
                f"{range_label(start, end)} · {bins[index]} 部"
                if has_value and not is_mobile(page)
                else None
            ),
            content=slot_content,
        )
        # 点击只绑定在柱子上，空白区域不响应点击。
        slot_bars.append(bar if has_value else None)
        return slot_container

    bars = ft.GestureDetector(
        on_long_press_start=show_hist_label,
        on_long_press_move_update=show_hist_label,
        on_long_press_end=end_hist,
        on_long_press_cancel=end_hist,
        content=ft.Row(
            width=hist_width,
            height=JOURNEY_HEIGHT,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[
                histogram_bar(index)
                for index in range(20)
            ],
        ),
    )

    async def reveal_histogram() -> None:
        if not hist_bars or not await wait_until_ready(page, bars):
            return
        for bar, target in hist_bars:
            bar.height = target
        try:
            page.update(*(bar for bar, _ in hist_bars))
        except RuntimeError:
            return
        except Exception:
            pass
    hist_labels = ft.Row(
        width=hist_width,
        spacing=0,
        controls=[
            ft.Container(
                width=slot,
                alignment=ft.Alignment.CENTER,
                content=ui_text(
                    str(index * 5),
                    size=7,
                    color=secondary,
                    no_wrap=True,
                ),
            )
            for index in range(20)
        ],
    )
    hist_content = ft.Column(
        width=hist_width,
        spacing=2,
        controls=[bars, hist_labels],
    )
    histogram = hist_content

    heat_controls: list[ft.Container] = []
    for index in range(20):
        heat_control = ft.Container(
            width=slot - 2,
            height=12,
            border_radius=2,
            bgcolor=ft.Colors.with_opacity(
                0.12 + 0.76 * (bins[index] / max_bin),
                accent,
            ),
            opacity=0 if animate else 1,
            scale=ft.Scale(1.4 if animate else 1.0),
            animate_opacity=(
                animation(220)
                if animate
                else None
            ),
            animate_scale=(
                animation(220)
                if animate
                else None
            ),
        )
        attach_heat_zoom(
            page,
            heat_control,
            initial_scale=1.4 if animate else 1.0,
        )
        heat_controls.append(heat_control)
    heat_cells = ft.Row(
        spacing=2,
        controls=heat_controls,
    )
    heat_legend = ft.Row(
        spacing=3,
        controls=[
            ui_text("Less", size=9, color=fg),
            *[
                ft.Container(
                    width=12,
                    height=12,
                    border_radius=2,
                    bgcolor=ft.Colors.with_opacity(opacity, accent),
                )
                for opacity in (0.18, 0.35, 0.52, 0.69, 0.86)
            ],
            ui_text("More", size=9, color=fg),
        ],
    )
    heat_row = ft.Column(
        spacing=4,
        controls=[heat_cells, heat_legend],
    )



    era_counts = {
        key: len(values)
        for key, values in era_quarters.items()
    }
    era_quarters, era_average = quarterly_series(era_quarters)

    def open_era_quarter(index: int) -> None:
        """打开该季度的作品列表。"""
        year, season_index = era_quarters[index]
        selected: list[Record] = []
        for record in records:
            date = earliest_broadcast_date(
                str(record.get("broadcast") or "")
            )
            if date is None:
                continue
            if (
                date[0] == year
                and quarter_for_month(date[1])[0] == season_index
            ):
                selected.append(record)
        route_q = (
            f"/statistics/rating/quarter/{year}/{season_index}"
        )
        title_q = quarter_label(year, season_index)

        def rebuild_q() -> ft.View:
            return build_quarter_works_view(
                page,
                load_records(),
                {},
                route_q,
                title=title_q,
                selected=selected,
            )

        view_q = build_quarter_works_view(
            page,
            load_records(),
            {},
            route_q,
            title=title_q,
            selected=selected,
            rebuild=rebuild_q,
        )
        if view_q is not None:
            push_view(page, view_q)

    if era_quarters:
        def era_tooltip(index: int) -> str:
            year, season = era_quarters[index]
            return (
                f"{year}{SEASONS[season]}"
                f" · 均分 {era_average[index]:.2f}"
                f" · {era_counts.get((year, season), 0)} 部"
            )

        era_chart, redraw_era = charts.line_chart(
            page,
            era_quarters,
            [(era_average, monthly_color)],
            tooltips=era_tooltip,
            limit=0 if animate else None,
            on_tap=open_era_quarter,
        )

        async def animate_era() -> None:
            if not await wait_until_ready(page, era_chart):
                redraw_era(limit=len(era_quarters))
                return
            if not (
                page.views
                and str(getattr(page.views[-1], "route", "")) == route
            ):
                return
            mark_seen(page, route)
            steps = ANIMATION_STEPS
            total = len(era_quarters)
            for step in range(1, steps + 1):
                eased = 1 - (1 - step / steps) ** 3
                limit = max(1, int(round(eased * total)))
                redraw_era(limit)
                await asyncio.sleep(ANIMATION_SECONDS / steps)
            redraw_era(total)

        if animate:
            page.run_task(animate_era)
    else:
        era_chart = ui_text(
            "无放送日期数据",
            size=12,
            color=secondary,
        )

    taste_months, taste_average = monthly_series(taste_pairs)
    taste_cumulative = cumulative_series(taste_months, taste_pairs)
    taste_counts: dict[tuple[int, int], int] = {}
    for date, _ in taste_pairs:
        key = (date[0], date[1])
        taste_counts[key] = taste_counts.get(key, 0) + 1
    taste_cumulative_counts: list[int] = []
    running = 0
    for key in taste_months:
        running += taste_counts.get(key, 0)
        taste_cumulative_counts.append(running)
    monthly_check = ft.Checkbox(
        label="月度平均",
        value=chart_toggles["monthly"],
    )
    cumulative_check = ft.Checkbox(
        label="累计平均",
        value=chart_toggles["cumulative"],
    )
    if taste_months:
        default_taste = max(360.0, 44.0 * len(taste_months))
        taste_width = fit_chart_width(page, default_taste)
        taste_slot = taste_width / max(1, len(taste_months))
        taste_canvas = fcanvas.Canvas(
            width=taste_width,
            height=JOURNEY_HEIGHT,
            shapes=[],
        )

        def taste_text(index: int) -> str:
            year, month = taste_months[index]
            count = taste_counts.get((year, month), 0)
            lines = [f"{year}.{month:02d}"]
            if monthly_check.value:
                lines.append(
                    f"月度平均 {taste_average[index]:.2f}"
                    f"（{count} 部）"
                )
            if cumulative_check.value:
                lines.append(
                    f"累计平均 {taste_cumulative[index]:.2f}"
                    f"（{taste_cumulative_counts[index]} 部）"
                )
            return "\n".join(lines)

        def open_taste_month(index: int) -> None:
            """打开该月份的补完列表。"""
            year, month = taste_months[index]
            open_completion_month(
                page,
                year,
                month,
                records=records,
            )

        taste_stack, refresh_taste = charts.chart_stack(
            page,
            width=taste_width,
            canvas=taste_canvas,
            count=len(taste_months),
            text_at=taste_text,
            slot=taste_slot,
            on_tap=open_taste_month,
        )

        def redraw_taste(
            event: ft.ControlEvent | None = None,
            *,
            limit: int | None = None,
        ) -> None:
            series: list[tuple[list[float], str]] = []
            if monthly_check.value:
                series.append((taste_average, monthly_color))
            if cumulative_check.value:
                series.append((taste_cumulative, cumulative_color))
            taste_canvas.shapes = charts.line_shapes(
                taste_months,
                series,
                slot=taste_slot,
                limit=limit,
            )
            try:
                taste_canvas.update()
            except Exception:
                pass
            refresh_taste()

        async def animate_taste() -> None:
            if not await wait_until_ready(page, taste_canvas):
                redraw_taste(limit=len(taste_months))
                return
            if not (
                page.views
                and str(getattr(page.views[-1], "route", "")) == route
            ):
                return
            mark_seen(page, route)
            steps = ANIMATION_STEPS
            total = len(taste_months)
            for step in range(1, steps + 1):
                eased = 1 - (1 - step / steps) ** 3
                limit = max(1, int(round(eased * total)))
                redraw_taste(limit=limit)
                await asyncio.sleep(ANIMATION_SECONDS / steps)
            redraw_taste(limit=total)

        def on_taste_toggle(event: ft.ControlEvent) -> None:
            chart_toggles["monthly"] = bool(monthly_check.value)
            chart_toggles["cumulative"] = bool(
                cumulative_check.value
            )
            redraw_taste(event)

        monthly_check.on_change = on_taste_toggle
        cumulative_check.on_change = on_taste_toggle
        taste_chart: ft.Control = taste_stack
        redraw_taste(limit=0 if animate else None)
        if animate:
            page.run_task(animate_taste)
    else:
        taste_chart = ui_text(
            "无补完日期数据",
            size=12,
            color=secondary,
        )

    classic_button = ft.Button(
        content=ui_text("殿堂经典", size=16),
        height=44,
        on_click=lambda event: open_rating_bars(
            page,
            ascending=False,
        ),
    )
    worst_button = ft.Button(
        content=ui_text("多大一坨", size=16),
        height=44,
        on_click=lambda event: open_rating_bars(
            page,
            ascending=True,
        ),
    )
    if is_wide(page):
        rating_buttons: ft.Control = ft.Row(
            alignment=ft.MainAxisAlignment.START,
            spacing=12,
            controls=[classic_button, worst_button],
        )
    else:
        classic_button.width = int(available)
        worst_button.width = int(available)
        rating_buttons = ft.Column(
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[classic_button, worst_button],
        )
    controls: list[ft.Control] = [
        ft.Container(
            width=int(available),
            content=ft.Column(spacing=10, controls=card_rows),
        ),
        ui_text(
            "分数分布",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=fg,
        ),
        histogram,
        heat_row,
        ui_text(
            "时代变迁（按放送起始）",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=fg,
        ),
        era_chart,
        ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ui_text(
                    "口味变化（按补完）",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=fg,
                ),
                monthly_check,
                cumulative_check,
            ],
        ),
        taste_chart,
        rating_buttons,
        ft.Container(height=48),
    ]
    view = _back_view(
        page,
        route="/statistics/ratings",
        title="评分",
        controls=[vertical_page(controls, spacing=10)],
        rebuild=lambda: rating_view(page),
    )
    view_data = view.data if isinstance(view.data, dict) else {}
    view_data["chart_toggles"] = chart_toggles
    view.data = view_data
    if animate:
        page.run_task(animate_heat_cells, page, heat_controls, seconds=ANIMATION_SECONDS)
        page.run_task(reveal_histogram)

    resize_state = {"token": 0, "scheduled": False}

    async def apply_resize() -> None:
        while True:
            token = resize_state["token"]
            await asyncio.sleep(0.08)
            if token == resize_state["token"]:
                break
        try:
            # 按 route 判断栈顶，避免重建后闭包绑定新视图导致失效。
            if (
                page.views
                and str(getattr(page.views[-1], "route", "")) == route
            ):
                mark_seen(page, route)
                new_view = rating_view(page)
                from bangumi.app import _attach_home_action

                _attach_home_action(page, new_view)
                # 复用旧滚动容器，避免滚动条闪回。
                if view.controls and new_view.controls:
                    old_column = view.controls[0]
                    new_column = new_view.controls[0]
                    try:
                        old_column.controls = new_column.controls
                    except Exception:
                        view.controls = new_view.controls
                else:
                    view.controls = new_view.controls
                view.appbar = new_view.appbar
                view.padding = new_view.padding
                if isinstance(new_view.data, dict):
                    view.data.update(new_view.data)
                # rating_view 重建会注册新闭包，这里覆盖回当前仍生效的 handler。
                register_resize_handler(page, route, on_resize)
                page.update()
        except RuntimeError:
            pass
        finally:
            resize_state["scheduled"] = False

    def on_resize(event=None) -> None:
        # 按 route 判断栈顶。
        if (
            not page.views
            or str(getattr(page.views[-1], "route", "")) != route
        ):
            return
        resize_state["token"] += 1
        if not resize_state["scheduled"]:
            resize_state["scheduled"] = True
            try:
                page.run_task(apply_resize)
            except RuntimeError:
                resize_state["scheduled"] = False

    register_resize_handler(page, route, on_resize)
    return view
