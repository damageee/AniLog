"""制作公司详情主页。"""

from __future__ import annotations

import random
import statistics as stats_lib
from urllib.parse import quote

import flet as ft
from bangumi.ui.anim import animation

from bangumi.core.utils import format_number
from bangumi.data.preferences import Preferences
from bangumi.ui import scroll_memory
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_entry,
    record_title,
    split_studios,
    split_tags,
)
from bangumi.ui.colors import foreground_color
from bangumi.ui.events import is_hover
from bangumi.ui.layout import vertical_page
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.ui.platform import is_compact_layout, is_mobile
from bangumi.ui.anim import wait_until_ready
from bangumi.ui.anim import (
    animation,
    entry_animations_enabled,
)
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.ui.tag_colors import FALLBACK_TAG_COLOR, is_valid_color
from bangumi.views.widgets.toast import copyable_title
from bangumi.ui.theme import ui_text
from bangumi.ui.interaction import FloatingLabel, hover_link
from bangumi.views.navigation import ENTRY, open_detail, push_view
from bangumi.data.statistics.studios_honor import (
    _honor_rating,
    _honor_year,
)
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    JOURNEY_BASELINE,
    JOURNEY_HEIGHT,
    JOURNEY_TOP,
    _accent,
    _back_view,
    range_label,
)
from bangumi.views.widgets.stat_card import stat_card
from bangumi.ui.constants import (
    ANIM_BASE_MS,
    HOVER_SCALE_BAR,
    HOVER_SCALE_TAG_CHIP,
)
from bangumi.views.general.detail_studio import build_studio_view
from bangumi.views.statistics.common.overlays import _hide_page_overlay


def open_studio_works(
    page: ft.Page,
    records: list[Record],
    company: str,
) -> None:
    """以共用的季度列表格式打开该公司的作品。"""
    name = str(company or "").strip()
    if not name:
        return
    route = f"/statistics/studios/works/{quote(name, safe='')}"
    if page.views and getattr(page.views[-1], "route", "") == route:
        return
    push_view(
        page,
        build_studio_view(
            page,
            records,
            {"studio": name},
            route,
            title=f"{name}（作品）",
            before=lambda: _hide_page_overlay(page),
        ),
    )


def _studio_bar_entries(
    page: ft.Page,
    records: list[Record],
    company_records: list[Record],
    keep,
) -> tuple[list[tuple[str, int]], dict[str, Record]]:
    valid: list[tuple[Record, int]] = []
    for record in company_records:
        rating = _honor_rating(record)
        if rating is None or rating <= 0 or not keep(rating):
            continue
        valid.append((record, rating))

    anime_counts: dict[str, int] = {}
    for record, _ in valid:
        anime = record_title(record)
        if anime:
            anime_counts[anime] = anime_counts.get(anime, 0) + 1

    entries: list[tuple[str, int]] = []
    works_by_label: dict[str, Record] = {}
    for index, (record, rating) in enumerate(valid):
        anime = record_title(record)
        entry = record_entry(record)
        label = anime
        if anime and anime_counts.get(anime, 0) > 1:
            label = f"{anime} · {entry or index}"
        base = label
        suffix = 2
        while label in works_by_label:
            label = f"{base} #{suffix}"
            suffix += 1
        works_by_label[label] = record
        entries.append((label, rating))
    return entries, works_by_label


def _studio_representatives(
    company_records: list[Record],
) -> list[Record]:
    def key(record: Record):
        rating = _honor_rating(record) or 0
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        date_key = (1, 0, 0, 0) if date is None else (0, *date)
        return (-rating, date_key)

    ranked = sorted(company_records, key=key)
    if not ranked:
        return []
    chosen = ranked[:3]
    if len(ranked) > 3:
        cutoff = key(ranked[2])
        if key(ranked[3]) == cutoff:
            better = [r for r in ranked[:3] if key(r) != cutoff]
            tied = [r for r in ranked if key(r) == cutoff]
            need = max(0, 3 - len(better))
            chosen = better + random.sample(
                tied,
                min(need, len(tied)),
            )
    return chosen[:3]


def _studio_overview_view(
    page: ft.Page,
    records: list[Record],
    name: str,
    company_records: list[Record],
    route: str,
) -> ft.View:
    from .works_range import _open_studio_range
    from .works_rankings import _open_studio_ratings
    from .works_tag import _open_studio_tag

    animate = entry_animations_enabled() and first_entry(page, route)
    if animate:
        mark_seen(page, route)
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    accent = _accent(page, "#2563EB", "#60A5FA")
    dark = page.theme_mode == ft.ThemeMode.DARK
    available = fit_chart_width(page, 1000.0, min_width=280.0)
    content_width = min(available, 520.0)
    narrow = is_compact_layout(page)

    ratings = [
        rating
        for record in company_records
        if (rating := _honor_rating(record)) is not None
    ]
    count = len(company_records)
    mean = float(stats_lib.fmean(ratings)) if ratings else None
    median = (
        float(stats_lib.median(ratings)) if ratings else None
    )
    max_rating = max(ratings) if ratings else None
    min_rating = min(ratings) if ratings else None
    years = sorted(
        {
            year
            for record in company_records
            if (year := _honor_year(record)) is not None
        }
    )
    if not years:
        year_span = "—"
    elif len(years) == 1:
        year_span = str(years[0])
    else:
        year_span = f"{years[0]}-{years[-1]}"

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
            ft.Row(
                spacing=12,
                controls=[card("作品数", f"{count} 部")],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card(
                        "平均分",
                        format_number(mean) if mean is not None else "—",
                    )
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card(
                        "中位数",
                        format_number(median) if median is not None else "—",
                    )
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card(
                        "最高分",
                        str(max_rating)
                        if max_rating is not None
                        else "—",
                    )
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card(
                        "最低分",
                        str(min_rating)
                        if min_rating is not None
                        else "—",
                    )
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[card("活跃年份跨度", year_span)],
            ),
        ]
    else:
        kpi_rows = [
            ft.Row(
                spacing=12,
                controls=[card("作品数", f"{count} 部")],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card(
                        "平均分",
                        format_number(mean) if mean is not None else "—",
                    ),
                    card(
                        "中位数",
                        format_number(median) if median is not None else "—",
                    ),
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card(
                        "最高分",
                        str(max_rating)
                        if max_rating is not None
                        else "—",
                    ),
                    card(
                        "最低分",
                        str(min_rating)
                        if min_rating is not None
                        else "—",
                    ),
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[card("活跃年份跨度", year_span)],
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

    slot = max(10.0, content_width / 20)
    hist_width = slot * 20
    bins = [0] * 20
    for value in ratings:
        bins[min(19, value // 5)] += 1
    max_bin = max(bins) or 1
    bar_height = JOURNEY_BASELINE - JOURNEY_TOP

    def _bar_hover(
        bar: ft.Container,
        event: ft.ControlEvent,
    ) -> None:
        hovered = is_hover(event)
        bar.scale = HOVER_SCALE_BAR if hovered else 1.0
        try:
            bar.update()
        except Exception:
            pass

    bar_slots: list[ft.Control] = []
    slot_bars: list[ft.Container | None] = []
    hist_bars: list[tuple[ft.Container, float]] = []
    hist_label = FloatingLabel(page)
    active_hist: dict[str, ft.Container | None] = {"bar": None}

    def scale_hist(target: ft.Container | None, on: bool) -> None:
        if target is None:
            return
        target.scale = HOVER_SCALE_BAR if on else 1.0
        try:
            target.update()
        except Exception:
            pass

    def show_hist_label(event: ft.ControlEvent) -> None:
        pos = getattr(event, "local_position", None)
        x = float(pos.x) if pos is not None else 0.0
        index = max(0, min(19, int(x // slot))) if slot else 0
        start = index * 5
        end = min(100, start + 5)
        count = bins[index]
        hist_label.show(
            event, f"{range_label(start, end)} · {count} 个"
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
    for index in range(20):
        start = index * 5
        end = min(100, start + 5)
        range_text = range_label(start, end)
        count = bins[index]
        label_text = f"{range_text} · {count} 个"
        colored = ft.Container(
            width=slot - 6,
            height=(
                0
                if animate
                else max(1.0, count / max_bin * bar_height)
            ),
            bgcolor=accent,
            border_radius=3,
            animate=(
                animation(int(ANIMATION_SECONDS * 1000))
                if animate
                else None
            ),
        )
        if count > 0:
            hist_bars.append(
                (
                    colored,
                    max(1.0, count / max_bin * bar_height),
                )
            )
        colored.animate_scale = animation(
            ANIM_BASE_MS, ft.AnimationCurve.EASE_OUT
        )
        colored.scale = 1.0
        if count > 0:
            bar_h = max(1.0, count / max_bin * bar_height)
            # 命中高度取柱高；短于 1/4 完整高度时才扩大。
            hit_h = max(bar_h, JOURNEY_HEIGHT / 4.0)
            hit_layer = ft.Container(
                width=slot - 6,
                height=hit_h,
                bgcolor=ft.Colors.TRANSPARENT,
                on_hover=lambda event, b=colored: _bar_hover(
                    b, event
                ),
                on_click=(
                    lambda event, s=start, e=end: _open_studio_range(
                        page,
                        records,
                        name,
                        company_records,
                        s,
                        e,
                    )
                ),
            )
            colored.bottom = 0.0
            slot_content = ft.Stack(
                width=slot - 6,
                height=hit_h,
                controls=[colored, hit_layer],
            )
        else:
            slot_content = ft.Container(width=slot - 6, height=0)
        slot_container = ft.Container(
            width=slot,
            height=JOURNEY_HEIGHT,
            alignment=ft.Alignment.BOTTOM_CENTER,
            tooltip=(
                label_text
                if count > 0 and not is_mobile(page)
                else None
            ),
            content=slot_content,
        )
        bar_slots.append(slot_container)
        slot_bars.append(colored if count > 0 else None)

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
            controls=bar_slots,
        ),
    )

    async def animate_histogram() -> None:
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

    if animate:
        page.run_task(animate_histogram)
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

    tag_counts: dict[str, int] = {}
    for record in company_records:
        for tag in split_tags(record.get("tag")):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags: list[tuple[str, int]] = []
    if tag_counts:
        ranked_tags = sorted(
            tag_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
        cutoff = sorted(
            tag_counts.values(), reverse=True
        )[:5]
        threshold = cutoff[-1] if cutoff else 0
        top_tags = [
            (tag, tag_count)
            for tag, tag_count in ranked_tags
            if tag_count >= threshold
        ]
    tag_colors = Preferences.load().tag_colors
    tag_chips: list[ft.Control] = []
    for tag, tag_count in top_tags:
        color = tag_colors.get(tag)
        if not is_valid_color(color):
            color = FALLBACK_TAG_COLOR
        chip = ft.Container(
            padding=ft.Padding.symmetric(
                horizontal=8,
                vertical=4,
            ),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.18, color),
            on_click=(
                lambda event, t=tag: _open_studio_tag(
                    page,
                    records,
                    name,
                    t,
                    company_records,
                )
            ),
            content=ui_text(
                f"{tag}（{tag_count}）",
                size=12,
                color=color,
            ),
        )
        chip.animate_scale = animation(
            ANIM_BASE_MS, ft.AnimationCurve.EASE_OUT
        )
        chip.scale = 1.0

        def on_chip_hover(
            event: ft.ControlEvent,
            target: ft.Container = chip,
        ) -> None:
            hovered = is_hover(event)
            target.scale = (
                HOVER_SCALE_TAG_CHIP if hovered else 1.0
            )
            try:
                target.update()
            except Exception:
                pass

        chip.on_hover = on_chip_hover

        def chip_long_start(
            event: ft.ControlEvent,
            target: ft.Container = chip,
        ) -> None:
            target.scale = ft.Scale(HOVER_SCALE_TAG_CHIP)
            try:
                target.update()
            except Exception:
                pass

        def chip_long_end(
            event: ft.ControlEvent,
            target: ft.Container = chip,
        ) -> None:
            target.scale = ft.Scale(1.0)
            try:
                target.update()
            except Exception:
                pass

        tag_chips.append(
            ft.GestureDetector(
                on_long_press_start=chip_long_start,
                on_long_press_end=chip_long_end,
                on_long_press_cancel=chip_long_end,
                content=chip,
            )
        )
    if not tag_chips:
        tag_chips = [ui_text("—", size=13, color=fg)]
    tags_row = ft.Row(
        wrap=True,
        spacing=6,
        run_spacing=6,
        width=content_width,
        controls=tag_chips,
    )

    buttons_row = ft.Row(
        spacing=12,
        width=content_width,
        controls=[
            ft.Container(
                expand=1,
                content=ft.Button(
                    content=ui_text("全部作品", size=15),
                    height=44,
                    on_click=lambda event: open_studio_works(
                        page,
                        records,
                        name,
                    ),
                ),
            ),
            ft.Container(
                expand=1,
                content=ft.Button(
                    content=ui_text("全部评分", size=15),
                    height=44,
                    on_click=lambda event: _open_studio_ratings(
                        page,
                        records,
                        name,
                        company_records,
                    ),
                ),
            ),
        ],
    )

    records_rep = _studio_representatives(company_records)
    if records_rep:
        rep_rows: list[ft.Control] = []
        for index, record in enumerate(records_rep, start=1):
            title = record_title(record)
            rep_rows.append(
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=36,
                            alignment=ft.Alignment.CENTER_RIGHT,
                            content=ui_text(
                                f"{index:02d}",
                                size=14,
                                color=secondary,
                                no_wrap=True,
                            ),
                        ),
                        ft.Container(
                            width=1,
                            height=20,
                            bgcolor=ft.Colors.with_opacity(0.25, fg),
                        ),
                        ft.Container(
                            expand=True,
                            alignment=ft.Alignment.CENTER_LEFT,
                            content=hover_link(
                                page,
                                ui_text(
                                    title,
                                    size=14,
                                    color=fg,
                                ),
                                fg,
                                lambda event, r=record: open_detail(
                                    page, records, r, ENTRY
                                ),
                            ),
                        ),
                    ],
                )
            )
        representative_row: ft.Control = ft.Column(
            width=content_width,
            spacing=6,
            controls=rep_rows,
        )
    else:
        representative_row = ui_text("—", size=13, color=fg)

    content: list[ft.Control] = [
        buttons_row,
        kpi_block,
        ui_text(
            "评分分布",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=fg,
        ),
        histogram,
        ui_text(
            "擅长TAG",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=fg,
        ),
        tags_row,
        ft.Row(
            width=content_width,
            controls=[
                ui_text(
                    "代表作品",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=fg,
                )
            ],
        ),
        representative_row,
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
    page_width = max(320.0, float(page.width or 1000) - 48.0)
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
    view = _back_view(
        page,
        route=route,
        title=name,
        controls=[vertical_page([centered], stretch=True)],
    )
    if view.appbar is not None:
        view.appbar.title = copyable_title(page, name)
    return view


def open_studio_page(
    page: ft.Page,
    records: list[Record],
    company: str,
) -> None:
    """从任意页面打开某公司的总览。"""
    name = str(company or "").strip()
    if not name:
        return
    route = "/statistics/studios/overview/" + quote(name, safe="")
    if (
        page.views
        and getattr(page.views[-1], "route", "") == route
    ):
        return
    company_records = [
        record
        for record in records
        if name in split_studios(record.get("studio"))
    ]

    def build_overview() -> ft.View:
        fresh = load_records()
        fresh_company = [
            record
            for record in fresh
            if name in split_studios(record.get("studio"))
        ]
        return _studio_overview_view(
            page,
            fresh,
            name,
            fresh_company,
            route,
        )

    state: dict[str, ft.View | None] = {"view": None}
    state["view"] = build_overview()
    state["view"].data = {
        "rebuild": lambda: _studio_overview_view(
            page,
            load_records(),
            name,
            [
                record
                for record in load_records()
                if name in split_studios(record.get("studio"))
            ],
            route,
        )
    }
    push_view(page, state["view"])

    def on_resize(event: ft.ControlEvent) -> None:
        # 按 route 判断栈顶，重建后仍能继续响应。
        if (
            not page.views
            or str(getattr(page.views[-1], "route", "")) != route
        ):
            return
        view = state["view"]
        if view is None or view not in page.views:
            return
        new_view = build_overview()
        # 复用旧视图与滚动容器，避免滚动条闪回。
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
        # 覆盖重建过程中可能注册的新 handler，保证后续 resize 继续执行。
        register_resize_handler(page, route, on_resize)
        page.update()
        scroll_memory.schedule_restore(page)

    register_resize_handler(page, route, on_resize)
