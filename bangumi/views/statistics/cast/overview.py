"""声优总览页。"""

from __future__ import annotations

import asyncio

from math import log2

import flet as ft
import flet.canvas as fcanvas

from bangumi.data import prework
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import load_records
from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import (
    ClickableText,
    FloatingLabel,
    hide_all_labels,
)
from bangumi.ui.layout import vertical_page
from bangumi.ui.layout import SCROLLBAR_WIDTH
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.ui.platform import is_compact_layout, is_mobile
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import push_view
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.views.statistics.common.shared import _accent, _back_view
from bangumi.views.statistics.rating.charts import smooth_path_elements
from bangumi.views.widgets.stat_card import stat_card
from .homepage import open_cast_homepage
from .homepage.roles_cowork import open_cast_roles_cowork


def _section_title(
    page: ft.Page,
    text: str,
    width: float,
) -> ft.Control:
    return ft.Row(
        width=width,
        controls=[
            ui_text(
                text,
                size=15,
                weight=ft.FontWeight.BOLD,
                color=foreground_color(page),
            )
        ],
    )


def cast_overview_view(page: ft.Page) -> ft.View:
    route = "/statistics/cast/overview"
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    accent = _accent(page, "#2563EB", "#60A5FA")
    available = fit_chart_width(page, 1000.0, min_width=280.0)
    content_width = min(available, 520.0)
    page_width = max(
        320.0,
        float(page.width or 1000) - 48.0 - SCROLLBAR_WIDTH,
    )
    narrow = is_compact_layout(page)
    mobile = is_mobile(page)

    records = load_records()
    index = prework.ensure_index(records)
    cv_works: dict[str, set[int]] = {}
    cv_first: dict[str, str] = {}
    for record_index, record in enumerate(records):
        for _character, cvs in prework._parse_role_lines(
            record.get("role")
        ):
            for cv in cvs:
                key = prework._normalize_name(cv)
                if not key:
                    continue
                cv_works.setdefault(key, set()).add(record_index)
                cv_first.setdefault(key, cv.strip())

    record_years: list[int | None] = []
    for record in records:
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        record_years.append(date[0] if date is not None else None)

    first_year: dict[str, int] = {}
    for key, works in cv_works.items():
        available = [
            record_years[index]
            for index in works
            if record_years[index] is not None
        ]
        if available:
            first_year[key] = min(available)
    last_year = max(
        (year for year in record_years if year is not None),
        default=None,
    )
    cohorts: dict[int, int] = {}
    for year in first_year.values():
        cohorts[year] = cohorts.get(year, 0) + 1
    years_window: list[int] = []
    if first_year and last_year is not None:
        years_window = list(
            range(min(first_year.values()), last_year + 1)
        )

    def survived(
        key: str,
        years: int,
    ) -> bool:
        start = first_year.get(key)
        if start is None:
            return False
        for work_index in cv_works.get(key, ()):
            year = record_years[work_index]
            if (
                year is not None
                and start < year <= start + years
            ):
                return True
        return False

    def survival_rate(
        year: int,
        years: int,
    ) -> float | None:
        total = cohorts.get(year, 0)
        if (
            total <= 0
            or last_year is None
            or year + years > last_year
        ):
            return None
        members = [
            key for key, value in first_year.items() if value == year
        ]
        if not members:
            return None
        return sum(
            1 for key in members if survived(key, years)
        ) / total

    rates1 = {
        year: survival_rate(year, 1) for year in years_window
    }
    rates3 = {
        year: survival_rate(year, 3) for year in years_window
    }

    total = len(cv_works)
    role_count = sum(len(roles) for roles in index.roles.values())
    ge2 = sum(1 for works in cv_works.values() if len(works) >= 2)
    ge5 = sum(1 for works in cv_works.values() if len(works) >= 5)
    ge10 = sum(1 for works in cv_works.values() if len(works) >= 10)
    ge50 = sum(1 for works in cv_works.values() if len(works) >= 50)

    def card(title: str, value: str) -> ft.Control:
        return stat_card(
            page,
            title,
            value,
            accent=accent,
            expand=1,
        )

    if narrow:
        kpi_rows = [
            ft.Row(spacing=12, controls=[card("总人数", str(total))]),
            ft.Row(spacing=12, controls=[card("角色数", str(role_count))]),
            ft.Row(spacing=12, controls=[card("≥2 部作品", str(ge2))]),
            ft.Row(spacing=12, controls=[card("≥5 部作品", str(ge5))]),
            ft.Row(spacing=12, controls=[card("≥10 部作品", str(ge10))]),
            ft.Row(spacing=12, controls=[card("≥50 部作品", str(ge50))]),
        ]
    else:
        kpi_rows = [
            ft.Row(
                spacing=12,
                controls=[
                    card("总人数", str(total)),
                    card("角色数", str(role_count)),
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card("≥2 部作品", str(ge2)),
                    card("≥5 部作品", str(ge5)),
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card("≥10 部作品", str(ge10)),
                    card("≥50 部作品", str(ge50)),
                ],
            ),
        ]
    kpi_block = ft.Container(
        width=int(content_width),
        content=ft.Column(
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=kpi_rows,
        ),
    )

    if cv_works:
        max_works = max(len(works) for works in cv_works.values())
        dist = [0] * (max_works + 1)
        for works in cv_works.values():
            dist[len(works)] += 1
        slot = content_width / max_works
        baseline = 140.0
        top = 12.0
        ys = [log2(dist[k] + 1) for k in range(1, max_works + 1)]
        max_yv = max(ys) or 1.0
        points = [
            (
                (k - 0.5) * slot,
                baseline
                - ys[k - 1] / max_yv * (baseline - top),
            )
            for k in range(1, max_works + 1)
        ]
        area_points = [
            (points[0][0], baseline),
            *points,
            (points[-1][0], baseline),
        ]
        area_elements = smooth_path_elements(area_points)
        area_elements.append(fcanvas.Path.Close())
        area = fcanvas.Path(
            elements=area_elements,
            paint=ft.Paint(
                color=ft.Colors.with_opacity(0.08, accent),
                style=ft.PaintingStyle.FILL,
            ),
        )
        line = fcanvas.Path(
            elements=smooth_path_elements(points),
            paint=ft.Paint(
                color=accent,
                stroke_width=2,
                style=ft.PaintingStyle.STROKE,
                stroke_cap=ft.StrokeCap.ROUND,
            ),
        )
        canvas = fcanvas.Canvas(
            width=content_width,
            height=160,
            shapes=[area, line],
        )
        heat_label = FloatingLabel(page)

        def show_long(event: ft.ControlEvent) -> None:
            pos = getattr(event, "local_position", None)
            x = float(pos.x) if pos is not None else 0.0
            k = max(1, min(max_works, int(x // slot) + 1))
            heat_label.show(event, f"{k} 部 · {dist[k]} 人")

        def end_long(event=None) -> None:
            heat_label.hide()

        slots = [
            ft.Container(
                width=slot,
                height=160,
                left=(k - 1) * slot,
                tooltip=None,
            )
            for k in range(1, max_works + 1)
        ]
        stack = ft.Stack(
            width=content_width,
            height=160,
            controls=[canvas, *slots],
        )
        if mobile:
            longtail: ft.Control = ft.GestureDetector(
                on_tap=show_long,
                on_tap_down=show_long,
                on_horizontal_drag_start=show_long,
                on_horizontal_drag_update=show_long,
                on_horizontal_drag_end=end_long,
                on_horizontal_drag_cancel=end_long,
                content=stack,
            )
        else:
            longtail = ft.GestureDetector(
                on_enter=show_long,
                on_hover=show_long,
                on_exit=end_long,
                hover_interval=40,
                content=stack,
            )
    else:
        longtail = ui_text("暂无数据", size=12, color=secondary)

    if years_window:
        survival_slot = content_width / len(years_window)
        baseline = 140.0
        top = 12.0
        max_count = max(cohorts.values(), default=0) or 1
        rate1_color = _accent(page, "#F59E0B", "#FBBF24")
        rate3_color = _accent(page, "#10B981", "#34D399")
        shapes: list[ft.Control] = []
        bars: list[ft.Control] = []
        for slot_index, year in enumerate(years_window):
            count = cohorts.get(year, 0)
            height = count / max_count * (baseline - top)
            if height > 0:
                bars.append(
                    ft.Container(
                        width=max(2.0, survival_slot - 4),
                        height=height,
                        left=slot_index * survival_slot + 2,
                        top=baseline - height,
                        border_radius=2,
                        bgcolor=ft.Colors.with_opacity(0.18, accent),
                    )
                )

        def survival_line(
            rates: dict[int, float | None],
            color: str,
        ) -> list[fcanvas.Path]:
            result: list[fcanvas.Path] = []
            segment: list[tuple[float, float]] = []
            for slot_index, year in enumerate(years_window):
                rate = rates.get(year)
                if rate is None:
                    continue  # 跳过 N/A，保持线段连续
                segment.append(
                    (
                        slot_index * survival_slot + survival_slot / 2,
                        baseline - rate * (baseline - top),
                    )
                )
            if len(segment) >= 2:
                result.append(_path(segment, color))
            return result

        def _path(
            points: list[tuple[float, float]],
            color: str,
        ) -> fcanvas.Path:
            return fcanvas.Path(
                elements=smooth_path_elements(points),
                paint=ft.Paint(
                    color=color,
                    stroke_width=2,
                    style=ft.PaintingStyle.STROKE,
                    stroke_cap=ft.StrokeCap.ROUND,
                ),
            )

        shapes.extend(survival_line(rates1, rate1_color))
        shapes.extend(survival_line(rates3, rate3_color))
        survival_label = FloatingLabel(page)

        def rate_text(rate: float | None) -> str:
            return "N/A" if rate is None else f"{rate * 100:.0f}%"

        def survival_text(year: int) -> str:
            count = cohorts.get(year, 0)
            return (
                f"{year} · {count} 人"
                f" · 1年 {rate_text(rates1.get(year))}"
                f" · 3年 {rate_text(rates3.get(year))}"
            )

        def show_survival(event: ft.ControlEvent) -> None:
            pos = getattr(event, "local_position", None)
            x = float(pos.x) if pos is not None else 0.0
            slot_index = (
                int(x // survival_slot) if survival_slot else 0
            )
            slot_index = max(
                0,
                min(len(years_window) - 1, slot_index),
            )
            survival_label.show(
                event, survival_text(years_window[slot_index])
            )

        def end_survival(event=None) -> None:
            survival_label.hide()

        slots = [
            ft.Container(
                width=survival_slot,
                height=160,
                left=slot_index * survival_slot,
                tooltip=None,
            )
            for slot_index, year in enumerate(years_window)
        ]
        survival_canvas = fcanvas.Canvas(
            width=content_width,
            height=160,
            shapes=list(shapes),
        )
        survival_stack = ft.Stack(
            width=content_width,
            height=160,
            controls=[*bars, survival_canvas, *slots],
        )
        if mobile:
            survival_chart: ft.Control = ft.GestureDetector(
                on_tap=show_survival,
                on_tap_down=show_survival,
                on_horizontal_drag_start=show_survival,
                on_horizontal_drag_update=show_survival,
                on_horizontal_drag_end=end_survival,
                on_horizontal_drag_cancel=end_survival,
                content=survival_stack,
            )
        else:
            survival_chart = ft.GestureDetector(
                on_enter=show_survival,
                on_hover=show_survival,
                on_exit=end_survival,
                hover_interval=40,
                content=survival_stack,
            )
        step = (len(years_window) + 5) // 6
        year_labels = ft.Row(
            width=content_width,
            spacing=0,
            controls=[
                ft.Container(
                    width=survival_slot,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        str(year) if slot_index % step == 0 else "",
                        size=7,
                        color=secondary,
                        no_wrap=True,
                    ),
                )
                for slot_index, year in enumerate(years_window)
            ],
        )

        def legend_item(color: str, text: str) -> ft.Control:
            return ft.Row(
                spacing=4,
                controls=[
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=2,
                        bgcolor=color,
                    ),
                    ui_text(text, size=10, color=secondary),
                ],
            )

        legend = ft.Row(
            spacing=12,
            width=content_width,
            controls=[
                legend_item(
                    ft.Colors.with_opacity(0.18, accent),
                    "人数",
                ),
                legend_item(rate1_color, "1 年留存"),
                legend_item(rate3_color, "3 年留存"),
            ],
        )
        survival_controls: list[ft.Control] = [
            _section_title(page, "初出茅庐", content_width),
            ui_text(
                "按首次出现年份分组：柱为人数，折线为 1 年 / 3 年留存率",
                size=11,
                color=secondary,
            ),
            survival_chart,
            year_labels,
            legend,
        ]
    else:
        survival_controls = [
            _section_title(page, "初出茅庐", content_width),
            ui_text("暂无数据", size=12, color=secondary),
        ]

    record_cvs: list[set[str]] = []
    for record in records:
        keys: set[str] = set()
        for _character, cvs in prework._parse_role_lines(
            record.get("role")
        ):
            for cv in cvs:
                key = prework._normalize_name(cv)
                if key:
                    keys.add(key)
        record_cvs.append(keys)

    pair_count: dict[tuple[str, str], int] = {}
    pair_last: dict[tuple[str, str], int] = {}
    for record_index, keys in enumerate(record_cvs):
        ordered = sorted(keys)
        year = record_years[record_index]
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1:]:
                pair = (left, right)
                pair_count[pair] = pair_count.get(pair, 0) + 1
                if year is not None:
                    previous = pair_last.get(pair)
                    pair_last[pair] = (
                        year if previous is None else max(previous, year)
                    )

    def display_name(key: str) -> str:
        return index.cowork_names.get(key, cv_first.get(key, key))

    partners: list[tuple[int, float, int | None, str, str, str, str]] = []
    for (left, right), count in pair_count.items():
        denom = min(
            len(cv_works.get(left, ())),
            len(cv_works.get(right, ())),
        )
        if denom <= 0:
            continue
        partners.append(
            (
                count,
                count / denom,
                pair_last.get((left, right)),
                display_name(left),
                display_name(right),
                left,
                right,
            )
        )
    partners.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            -(item[2] if item[2] is not None else -1),
            item[3],
            item[4],
        )
    )
    ranked: list[tuple[int, tuple]] = []
    previous_key = None
    rank = 0
    for position, item in enumerate(partners, start=1):
        rank_key = (item[0], item[1], item[2])
        if rank_key != previous_key:
            rank = position
            previous_key = rank_key
        if rank > 10:
            break
        ranked.append((rank, item))

    # 按名字实际需要分配 A/B 两列；窄屏压缩固定列。
    name_size = 11 if narrow else 12
    rank_w = 22.0 if narrow else 26.0
    count_w = 52.0 if narrow else 64.0
    rate_w = 34.0 if narrow else 40.0
    last_w = 40.0 if narrow else 48.0
    spacing = 4.0 if narrow else 6.0
    name_a_w = max(
        (
            text_width(str(item[3]), size=name_size)
            for _, item in ranked
        ),
        default=0.0,
    )
    name_b_w = max(
        (
            text_width(str(item[4]), size=name_size)
            for _, item in ranked
        ),
        default=0.0,
    )
    need_a = max(
        text_width("友人 A", size=11), name_a_w
    ) + 6
    need_b = max(
        text_width("友人 B", size=11), name_b_w
    ) + 6
    avail = max(
        0.0,
        float(content_width)
        - (rank_w + count_w + rate_w + last_w)
        - spacing * 5,
    )
    total_need = need_a + need_b
    if total_need <= 0:
        a_w = b_w = max(40.0, avail / 2)
    elif total_need <= avail:
        a_w = need_a
        b_w = need_b
    else:
        scale = avail / total_need
        a_w = need_a * scale
        b_w = need_b * scale
    gap = spacing

    table_width = (
        rank_w
        + count_w
        + rate_w
        + last_w
        + a_w
        + b_w
        + gap * 5
    )

    header = ft.Row(
        width=table_width,
        spacing=gap,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(width=rank_w, content=ui_text("排名", size=11, color=secondary, no_wrap=True)),
            ft.Container(width=a_w, content=ui_text("友人 A", size=11, color=secondary, no_wrap=True)),
            ft.Container(width=b_w, content=ui_text("友人 B", size=11, color=secondary, no_wrap=True)),
            ft.Container(width=count_w, alignment=ft.Alignment.CENTER_RIGHT, content=ui_text("合作数", size=11, color=secondary, no_wrap=True)),
            ft.Container(width=rate_w, alignment=ft.Alignment.CENTER_RIGHT, content=ui_text("合作率", size=11, color=secondary, no_wrap=True)),
            ft.Container(width=last_w, alignment=ft.Alignment.CENTER_RIGHT, content=ui_text("最近", size=11, color=secondary, no_wrap=True)),
        ],
    )
    partner_rows: list[ft.Control] = []
    for rank_value, item in ranked:
        count, rate, last, name_a, name_b, _key_a, _key_b = item
        partner_rows.append(
            ft.Row(
                spacing=gap,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=rank_w,
                        content=ui_text(
                            str(rank_value), size=12, color=secondary, no_wrap=True
                        ),
                    ),
                    ft.Container(
                        width=a_w,
                        content=ClickableText(
                            page,
                            name_a,
                            size=name_size,
                            no_wrap=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            on_click=(
                                lambda event, n=name_a: open_cast_homepage(
                                    page, records, n
                                )
                            ),
                        ).control,
                    ),
                    ft.Container(
                        width=b_w,
                        content=ClickableText(
                            page,
                            name_b,
                            size=name_size,
                            no_wrap=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            on_click=(
                                lambda event, n=name_b: open_cast_homepage(
                                    page, records, n
                                )
                            ),
                        ).control,
                    ),
                    ft.Container(
                        width=count_w,
                        alignment=ft.Alignment.CENTER_RIGHT,
                        content=ClickableText(
                            page,
                            str(count),
                            size=12,
                            no_wrap=True,
                            on_click=(
                                lambda event, a=name_a, b=name_b: (
                                    open_cast_roles_cowork(
                                        page,
                                        records,
                                        a,
                                        b,
                                        hide_score=True,
                                    )
                                )
                            ),
                        ).control,
                    ),
                    ft.Container(
                        width=rate_w,
                        alignment=ft.Alignment.CENTER_RIGHT,
                        content=ui_text(f"{rate:.2f}", size=12, color=fg, no_wrap=True),
                    ),
                    ft.Container(
                        width=last_w,
                        alignment=ft.Alignment.CENTER_RIGHT,
                        content=ui_text(
                            str(last) if last is not None else "—",
                            size=12,
                            color=fg,
                            no_wrap=True,
                        ),
                    ),
                ],
            )
        )
    partner_controls: list[ft.Control] = [
        _section_title(page, "合作伙伴", content_width),
    ]
    if partner_rows:
        divider = ft.Container(
            width=table_width,
            height=1,
            bgcolor=ft.Colors.with_opacity(0.2, fg),
        )
        rows_column = ft.Column(
            spacing=8,
            width=table_width,
            controls=partner_rows,
        )
        table_body = ft.Column(
            width=table_width,
            spacing=8,
            controls=[header, divider, rows_column],
        )
        # 窄窗口下允许横向滚动查看完整表格。
        table_scroll = ft.Row(
            width=content_width,
            scroll=ft.ScrollMode.AUTO,
            controls=[table_body],
        )
        partner_controls.append(table_scroll)
    else:
        partner_controls.append(
            ui_text("暂无合作数据", size=12, color=secondary)
        )

    content: list[ft.Control] = [
        kpi_block,
        _section_title(page, "作品数长尾分布", content_width),
        longtail,
        *survival_controls,
        *partner_controls,
        ft.Row(
            width=content_width,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ui_text(
                    "数据仅来源于用户的个人记录",
                    size=11,
                    color=secondary,
                )
            ],
        ),
    ]
    centered = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
        width=page_width,
        controls=[
            ft.Column(
                width=content_width,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=content,
            )
        ],
    )
    page_gesture = ft.GestureDetector(
        expand=True,
        on_tap=lambda event: hide_all_labels(page),
        content=vertical_page([centered], stretch=True),
    )
    view = _back_view(
        page,
        route=route,
        title="声优 —— 总览",
        controls=[page_gesture],
        rebuild=lambda: cast_overview_view(page),
    )

    resize_token = {"value": 0}

    def on_overview_resize(event=None) -> None:
        if (
            not page.views
            or str(getattr(page.views[-1], "route", "")) != route
        ):
            return
        resize_token["value"] += 1
        token = resize_token["value"]

        async def apply() -> None:
            await asyncio.sleep(0.12)
            if resize_token["value"] != token:
                return
            if (
                not page.views
                or str(getattr(page.views[-1], "route", "")) != route
            ):
                return
            from bangumi.ui.interaction import hide_all_labels

            try:
                hide_all_labels(page)
            except Exception:
                pass
            new_view = cast_overview_view(page)
            top = page.views[-1]
            top.controls = new_view.controls
            top.appbar = new_view.appbar
            top.padding = new_view.padding
            if isinstance(new_view.data, dict):
                if not isinstance(top.data, dict):
                    top.data = {}
                top.data.update(new_view.data)
            try:
                page.update()
            except Exception:
                pass
            try:
                hide_all_labels(page)
            except Exception:
                pass

        page.run_task(apply)

    register_resize_handler(page, route, on_overview_resize)
    return view


def open_cast_overview(page: ft.Page) -> None:
    """打开声优总览页。"""
    view = cast_overview_view(page)
    if page.views and getattr(page.views[-1], "route", "") == view.route:
        return
    push_view(page, view)
