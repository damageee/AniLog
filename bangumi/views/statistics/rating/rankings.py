"""评分统计与评分榜单页。"""

from __future__ import annotations

import flet as ft
from bangumi.io.importer import (
    CATEGORY_OPTIONS,
)
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.text_metrics import text_width
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.views.general.bar_chart import (
    random_bar_colors,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.platform import is_mobile, is_wide
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover
from bangumi.ui.constants import ANIM_BASE_MS, HOVER_SCALE_BAR
from bangumi.ui.interaction import FloatingLabel
from bangumi.views.navigation import ENTRY, open_detail, push_view
from bangumi.ui.layout import (
    vertical_page,
)
from bangumi.data.quarter_core import (
    earliest_broadcast_date,
)
from bangumi.data.watched_data import (
    load_records,
    record_title,
)
from bangumi.views.statistics.common.shared import (
    _back_view,
)


TOP_COUNTS: tuple[int, ...] = (
    5,
    10,
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    60,
    70,
    80,
    90,
    100,
)


def open_rating_bars(
    page: ft.Page,
    *,
    ascending: bool,
) -> None:
    view = _rating_bars_view(page, ascending=ascending)
    if page.views and getattr(page.views[-1], "route", "") == view.route:
        return
    push_view(page, view)


def _rating_bars_view(
    page: ft.Page,
    *,
    ascending: bool,
) -> ft.View:
    records = load_records()
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    route = (
        "/statistics/ratings/worst"
        if ascending
        else "/statistics/ratings/best"
    )
    title = "多大一坨" if ascending else "殿堂经典"

    entries: list[tuple[int, str, int | None, str, dict]] = []
    for record in records:
        raw = str(record.get("rating") or "").strip()
        try:
            score = int(raw)
        except ValueError:
            continue
        if not 0 <= score <= 100:
            continue
        name = record_title(record)
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        year = date[0] if date is not None else None
        category = str(record.get("category") or "").strip() or "其他"
        entries.append((score, name, year, category, record))
    entries.sort(
        key=lambda item: (
            item[0] if ascending else -item[0],
            item[1],
        )
    )

    if not entries:
        return _back_view(
            page,
            route=route,
            title=title,
            rebuild=lambda: _rating_bars_view(
                page, ascending=ascending
            ),
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

    years = sorted(
        {
            year
            for _, _, year, _, _ in entries
            if year is not None
        },
        reverse=True,
    )
    year_options = ["全部年份", *[str(year) for year in years]]
    category_options = ["全部类别", *CATEGORY_OPTIONS]

    def make_menu(
        options: list[str],
        width: int,
    ) -> tuple[ft.PopupMenuButton, dict[str, str]]:
        state = {"value": options[0]}
        label = ui_text(options[0], size=12, color=fg)

        def select(value: str) -> None:
            state["value"] = value
            label.value = value
            try:
                label.update()
            except Exception:
                pass
            apply_filters()

        button = ft.PopupMenuButton(
            content=ft.Container(
                width=width,
                height=30,
                padding=ft.Padding.symmetric(horizontal=8),
                border=ft.Border.all(
                    1,
                    ft.Colors.with_opacity(0.35, fg),
                ),
                border_radius=6,
                alignment=ft.Alignment.CENTER,
                content=ft.Row(
                    spacing=4,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        label,
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
                    content=ui_text(option, size=12),
                    on_click=lambda event, v=option: select(v),
                )
                for option in options
            ],
        )
        return button, state

    year_button, year_state = make_menu(year_options, 118)
    category_button, category_state = make_menu(category_options, 118)

    def active_entries() -> list[tuple[int, str, object]]:
        year_value = year_state["value"]
        category_value = category_state["value"]
        chosen = [
            (score, name, record)
            for score, name, year, category, record in entries
            if (
                year_value == "全部年份"
                or str(year) == year_value
            )
            and (
                category_value == "全部类别"
                or category == category_value
            )
        ]
        chosen.sort(
            key=lambda item: (
                item[0] if ascending else -item[0],
                item[1],
            )
        )
        return chosen

    reserve_width = {"value": 0.0}

    def available_width() -> float:
        page_w = float(page.width or 1000)
        return max(60.0, page_w - 48.0 - reserve_width["value"])

    bar_controls: list[tuple[ft.Container, int]] = []
    rank_label = FloatingLabel(page)
    active_bar: dict[str, ft.Container | None] = {"bar": None}
    pitch = 48.0

    def scale_bar(target: ft.Container, on: bool) -> None:
        target.scale = HOVER_SCALE_BAR if on else 1.0
        try:
            target.update()
        except Exception:
            pass

    def build_items(limit: int) -> list[ft.Control]:
        bar_controls.clear()
        active_bar["bar"] = None
        controls: list[ft.Control] = []
        colors = random_bar_colors(limit)
        chosen = active_entries()
        texts = [str(item[0]) for item in chosen[:limit]]
        reserve_width["value"] = max(
            text_width("00000000", size=12),
            max(
                (text_width(t, size=12) for t in texts),
                default=0.0,
            ),
        ) + 12.0
        for index, (score, name, record) in enumerate(chosen[:limit]):
            color = colors[index]
            bar_width = max(4, int(available_width() * score / 100))
            bar = ft.Container(
                width=bar_width,
                height=22,
                border_radius=4,
                bgcolor=color,
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

            bar_controls.append((bar, score))
            text_w = float(text_width(str(score), size=12))
            full = available_width()
            # 命中区取柱子实际长度；只有短于 1/4 完整长度时才扩大。
            hit_width = (
                bar_width if bar_width >= full / 4.0 else full / 4.0
            )
            row_width = max(
                hit_width,
                bar_width + (8.0 + text_w if text_w else 0.0),
            )
            hit_layer = ft.Container(
                width=hit_width,
                height=22,
                bgcolor=ft.Colors.TRANSPARENT,
                tooltip=None if is_mobile(page) else name,
                on_hover=lambda event, b=bar: on_bar_hover(event, b),
                on_click=(
                    lambda event, r=record: open_detail(
                        page,
                        records,
                        r,
                        ENTRY,
                    )
                ),
            )
            bar_row = ft.Stack(
                width=row_width,
                height=22,
                clip_behavior=ft.ClipBehavior.NONE,
                controls=[
                    bar,
                    hit_layer,
                    # 分值文字绝对定位，保持 8px 间距且不参与命中。
                    ft.Container(
                        left=bar_width + 8.0,
                        top=0,
                        height=22,
                        ignore_interactions=True,
                        alignment=ft.Alignment.CENTER_LEFT,
                        content=ui_text(str(score), size=12, color=fg),
                    ),
                ],
            )
            column = ft.Column(
                spacing=2,
                controls=[
                    bar_row,
                    ui_text(
                        name,
                        size=11,
                        color=secondary,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            )
            def show_name(
                event: ft.ControlEvent,
                display_name: str = name,
                bar_index: int = index,
            ) -> None:
                rank_label.show(event, display_name)
                scale_bar(bar_controls[bar_index][0], True)
                active_bar["bar"] = bar_controls[bar_index][0]

            def move_name(
                event: ft.ControlEvent,
                base_index: int = index,
            ) -> None:
                offset = getattr(
                    event, "local_offset_from_origin", None
                )
                if offset is None:
                    offset = getattr(event, "offset_from_origin", None)
                if offset is None:
                    return
                dy = float(getattr(offset, "y", 0) or 0)
                target = base_index + int(round(dy / pitch))
                target = max(0, min(len(chosen) - 1, target))
                current = active_bar["bar"]
                if current is not None:
                    scale_bar(current, False)
                rank_label.show(event, chosen[target][1])
                scale_bar(bar_controls[target][0], True)
                active_bar["bar"] = bar_controls[target][0]

            def end_long(event: ft.ControlEvent) -> None:
                current = active_bar["bar"]
                if current is not None:
                    scale_bar(current, False)
                active_bar["bar"] = None
                rank_label.hide()

            controls.append(
                ft.GestureDetector(
                    on_long_press_start=show_name,
                    on_long_press_move_update=move_name,
                    on_long_press_end=end_long,
                    on_long_press_cancel=end_long,
                    content=ft.Container(
                        height=38,
                        content=column,
                    ),
                )
            )
        return controls

    current_top = {"value": 1}
    holder = ft.Column(spacing=10, controls=build_items(TOP_COUNTS[1]))
    top_label = ui_text(f"Top {TOP_COUNTS[1]}", size=13, color=fg)

    def apply_filters() -> None:
        holder.controls = build_items(TOP_COUNTS[current_top["value"]])
        try:
            holder.update()
        except Exception:
            pass

    def on_slide(event: ft.ControlEvent) -> None:
        try:
            index = int(round(float(event.control.value or 0)))
        except (TypeError, ValueError):
            index = 1
        index = max(0, min(len(TOP_COUNTS) - 1, index))
        current_top["value"] = index
        top_label.value = f"Top {TOP_COUNTS[index]}"
        slider.label = str(TOP_COUNTS[index])
        apply_filters()
        try:
            top_label.update()
        except Exception:
            pass
        try:
            slider.update()
        except Exception:
            pass

    slider = ft.Slider(
        min=0,
        max=len(TOP_COUNTS) - 1,
        divisions=len(TOP_COUNTS) - 1,
        value=1,
        label=str(TOP_COUNTS[1]),
        expand=True,
        on_change=on_slide,
    )
    slider_row = ft.Row(
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[top_label, slider],
    )

    if is_wide(page):
        layout_controls: list[ft.Control] = [
            slider_row,
            ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[year_button, category_button],
            ),
            ft.Container(height=18),
            holder,
        ]
    else:
        layout_controls = [
            ft.Row(controls=[top_label]),
            ft.Row(controls=[slider]),
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[year_button, category_button],
            ),
            ft.Container(height=18),
            holder,
        ]

    view = _back_view(
        page,
        route=route,
        title=title,
        rebuild=lambda: _rating_bars_view(
            page, ascending=ascending
        ),
        controls=[
            vertical_page(
                layout_controls,
                spacing=12,
            )
        ],
    )
    def on_resize(event=None) -> None:
        # 仅栈顶响应
        if view not in page.views or page.views[-1] is not view:
            return
        width = available_width()
        for bar, score in bar_controls:
            bar.width = max(4, int(width * score / 100))
        try:
            holder.update()
        except Exception:
            pass

    register_resize_handler(page, route, on_resize)
    return view
