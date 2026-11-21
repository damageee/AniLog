"""年度报告页。

按年份（或「总览」）汇总补完记录，展示 KPI、每月酬勤、
最爱标签、个人品味与 轻松总结。
"""

from __future__ import annotations

import datetime as dt
import random
import statistics as stats_lib
from urllib.parse import quote

import flet as ft

from bangumi.core.utils import format_number
from bangumi.data.dates import parse_iso_date
from bangumi.data.prework import _spec_episode_parts
from bangumi.data.ratings import parse_rating
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_entry,
    record_title,
    split_tags,
)
from bangumi.ui.anim import animation
from bangumi.ui.colors import foreground_color
from bangumi.ui.constants import ANIM_BASE_MS, HOVER_SCALE_BAR
from bangumi.ui.events import is_hover
from bangumi.ui.interaction import FloatingLabel
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.ui.layout import vertical_page
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text
from bangumi.views.general.bar_chart import (
    build_bar_chart_view,
    random_bar_colors,
)
from bangumi.views.general.detail_completion import open_completion_month
from bangumi.views.general.detail_tag import build_tag_view
from bangumi.views.navigation import ENTRY, open_detail, push_view
from bangumi.views.statistics.common.shared import (
    JOURNEY_BASELINE,
    JOURNEY_HEIGHT,
    JOURNEY_TOP,
    _accent,
    _back_view,
    range_label,
)
from bangumi.views.widgets.stat_card import stat_card

# 柱状图可用高度（与旅途曲线保持一致）。
BAR_HEIGHT = JOURNEY_BASELINE - JOURNEY_TOP


def _report_year(name: str) -> int | None:
    """解析报告年份；「总览」或非数字名称返回 ``None``。"""
    text = str(name or "").strip()
    if not text or text == "总览":
        return None
    if not text.isdigit():
        return None
    return int(text)


def _fmt_amount(value: float) -> str:
    """整数输出整数，否则保留 1 位小数。"""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def annual_report_view(page: ft.Page, name: str) -> ft.View:
    """年度报告页。"""
    route = "/statistics/annual/" + quote(name, safe="")
    year = _report_year(name)
    records = load_records()

    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    accent = _accent(page, "#2563EB", "#60A5FA")

    available = fit_chart_width(page, 1000.0, min_width=280.0)
    content_width = min(available, 520.0)

    # 按补完日期筛选作用域内的作品。
    dated: list[tuple[Record, dt.date]] = []
    for record in records:
        date = parse_iso_date(str(record.get("completion") or ""))
        if date is None:
            continue
        if year is not None and date.year != year:
            continue
        dated.append((record, date))
    works: list[Record] = [record for record, _ in dated]

    def section(text: str) -> ft.Control:
        """章节标题。"""
        return ft.Row(
            width=content_width,
            controls=[
                ui_text(
                    text,
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=fg,
                )
            ],
        )

    # ---------------- KPI ----------------
    total_episodes = 0.0
    total_minutes = 0.0
    for record in works:
        episodes, minutes = _spec_episode_parts(
            record.get("specification"),
        )
        total_episodes += episodes
        total_minutes += minutes
    # 话数与分钟分开统计：话数不含分钟。
    if total_episodes > 0 and total_minutes > 0:
        episodes_text = (
            f"{_fmt_amount(total_episodes)}集"
            f" + {_fmt_amount(total_minutes)}分钟"
        )
    elif total_episodes > 0:
        episodes_text = f"{_fmt_amount(total_episodes)}集"
    elif total_minutes > 0:
        episodes_text = f"{_fmt_amount(total_minutes)}分钟"
    else:
        episodes_text = "—"

    scored: list[tuple[Record, int]] = []
    for record in works:
        rating = parse_rating(record.get("rating"))
        if rating is None:
            continue
        scored.append((record, rating))
    ratings = [rating for _, rating in scored]
    mean = float(stats_lib.fmean(ratings)) if ratings else None
    best_record: Record | None = None
    best_score: int | None = None
    if scored:
        best_record, best_score = max(
            scored,
            key=lambda item: item[1],
        )

    def card(title: str, value: str) -> ft.Control:
        return stat_card(
            page,
            title,
            value,
            accent=accent,
            expand=1,
        )

    kpi_rows: list[ft.Control] = [
        ft.Row(
            spacing=12,
            controls=[card("部数", f"{len(works)} 部")],
        ),
        ft.Row(
            spacing=12,
            controls=[card("集数", episodes_text)],
        ),
        ft.Row(
            spacing=12,
            controls=[
                card(
                    "均分",
                    format_number(mean) if mean is not None else "—",
                )
            ],
        ),
        ft.Row(
            spacing=12,
            controls=[
                card(
                    "最高分",
                    str(best_score)
                    if best_score is not None
                    else "—",
                )
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

    # ---------------- 通用柱状图交互 ----------------
    def hover_bar(
        bar: ft.Container,
        event: ft.ControlEvent,
    ) -> None:
        hovered = is_hover(event)
        bar.scale = HOVER_SCALE_BAR if hovered else 1.0
        try:
            bar.update()
        except Exception:
            pass

    # ---------------- 每月酬勤 ----------------
    month_counts: dict[int, int] = {
        month: 0 for month in range(1, 13)
    }
    for _, date in dated:
        month_counts[date.month] += 1
    month_max = max(month_counts.values()) or 1
    month_slot = content_width / 12
    month_label = FloatingLabel(page)
    month_slots: list[ft.Control] = []
    for month in range(1, 13):
        count = month_counts[month]
        bar = ft.Container(
            width=max(4.0, month_slot - 6),
            height=(
                count / month_max * BAR_HEIGHT
                if count > 0
                else 0
            ),
            bgcolor=accent,
            border_radius=3,
        )
        bar.animate_scale = animation(
            ANIM_BASE_MS,
            ft.AnimationCurve.EASE_OUT,
        )
        bar.scale = 1.0
        if count > 0:
            bar_w = float(bar.width or 0.0)
            bar_h = float(bar.height or 0.0)
            # 命中高度取柱高；短于 1/4 完整高度时才扩大。
            hit_h = max(bar_h, JOURNEY_HEIGHT / 4.0)
            hit_layer = ft.Container(
                width=bar_w,
                height=hit_h,
                bgcolor=ft.Colors.TRANSPARENT,
                on_hover=lambda event, b=bar: hover_bar(b, event),
                on_click=(
                    (
                        lambda event, m=month, y=year: (
                            open_completion_month(
                                page,
                                y,
                                m,
                                records=records,
                            )
                        )
                    )
                    if year is not None
                    else None
                ),
            )
            bar.bottom = 0.0
            slot_content = ft.Stack(
                width=bar_w,
                height=hit_h,
                controls=[bar, hit_layer],
            )
        else:
            slot_content = ft.Container(
                width=max(4.0, month_slot - 6),
                height=0,
            )
        month_slots.append(
            ft.Container(
                width=month_slot,
                height=JOURNEY_HEIGHT,
                alignment=ft.Alignment.BOTTOM_CENTER,
                tooltip=(
                    f"{month}月 · {count} 部"
                    if count > 0
                    else None
                ),
                content=slot_content,
            )
        )

    def month_at(event: ft.ControlEvent) -> int:
        pos = getattr(event, "local_position", None)
        x = float(pos.x) if pos is not None else 0.0
        index = int(x // month_slot) if month_slot else 0
        index = max(0, min(11, index))
        return index + 1

    def show_month_label(event: ft.ControlEvent) -> None:
        month = month_at(event)
        month_label.show(
            event,
            f"{month}月 · {month_counts[month]} 部",
        )

    def hide_month_label() -> None:
        month_label.hide()

    month_bars = ft.GestureDetector(
        on_long_press_start=show_month_label,
        on_long_press_move_update=show_month_label,
        on_long_press_end=hide_month_label,
        on_long_press_cancel=hide_month_label,
        content=ft.Row(
            width=content_width,
            height=JOURNEY_HEIGHT,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=month_slots,
        ),
    )
    month_labels = ft.Row(
        width=content_width,
        spacing=0,
        controls=[
            ft.Container(
                width=month_slot,
                alignment=ft.Alignment.CENTER,
                content=ui_text(
                    str(month),
                    size=7,
                    color=secondary,
                    no_wrap=True,
                ),
            )
            for month in range(1, 13)
        ],
    )
    monthly_block = ft.Column(
        width=content_width,
        spacing=2,
        controls=[month_bars, month_labels],
    )

    # ---------------- 最爱标签 ----------------
    tag_counts: dict[str, int] = {}
    tagged_total = 0
    for record in works:
        tags = split_tags(record.get("tag"))
        if tags:
            tagged_total += 1
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    top_tags = sorted(
        tag_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:5]

    def open_tag(tag: str) -> None:
        target = next(
            (
                record
                for record in works
                if tag in split_tags(record.get("tag"))
            ),
            None,
        )
        if target is None:
            return
        tag_route = (
            "/statistics/annual/"
            + quote(name, safe="")
            + "/tag/"
            + quote(tag, safe="")
        )
        if (
            page.views
            and getattr(page.views[-1], "route", "") == tag_route
        ):
            return
        push_view(
            page,
            build_tag_view(
                page,
                records,
                target,
                tag_route,
                year=year,
                tag=tag,
                title=f"{tag}（{name}）",
            ),
        )

    tag_rows: list[ft.Control] = []
    if top_tags:
        tag_colors = random_bar_colors(len(top_tags))
        tag_max = top_tags[0][1] or 1
        # 预留右侧数值文字的位置。
        bar_area = max(40.0, content_width - 48)
        for index, (tag, tag_count) in enumerate(top_tags):
            color = tag_colors[index]
            bar = ft.Container(
                width=max(2.0, bar_area * tag_count / tag_max),
                height=22,
                border_radius=4,
                bgcolor=color,
            )
            bar.animate_scale = animation(
                ANIM_BASE_MS,
                ft.AnimationCurve.EASE_OUT,
            )
            bar.scale = 1.0
            tag_name = ui_text(
                tag,
                size=11,
                color=secondary,
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
            bar_w = float(bar.width or 0.0)
            text_w = float(text_width(str(tag_count), size=12))
            # 命中区取柱子实际长度；只有短于 1/4 完整长度时才扩大。
            hit_width = (
                bar_w if bar_w >= bar_area / 4.0 else bar_area / 4.0
            )
            row_width = max(
                hit_width,
                bar_w + (8.0 + text_w if text_w else 0.0),
            )
            hit_layer = ft.Container(
                width=hit_width,
                height=22,
                bgcolor=ft.Colors.TRANSPARENT,
                on_hover=lambda event, b=bar: hover_bar(b, event),
                on_click=lambda event, t=tag: open_tag(t),
            )
            bar_row = ft.Stack(
                width=row_width,
                height=22,
                clip_behavior=ft.ClipBehavior.NONE,
                controls=[
                    bar,
                    hit_layer,
                    # 数值文字绝对定位，保持 8px 间距且不参与命中。
                    ft.Container(
                        left=bar_w + 8.0,
                        top=0,
                        height=22,
                        ignore_interactions=True,
                        alignment=ft.Alignment.CENTER_LEFT,
                        content=ui_text(
                            str(tag_count),
                            size=12,
                            color=fg,
                        ),
                    ),
                ],
            )
            tag_rows.append(
                ft.Column(
                    width=content_width,
                    spacing=2,
                    controls=[
                        bar_row,
                        tag_name,
                    ],
                )
            )
    else:
        tag_rows = [
            ft.Row(
                width=content_width,
                controls=[
                    ui_text("暂无数据", size=12, color=secondary)
                ],
            )
        ]
    tags_block = ft.Column(
        width=content_width,
        spacing=8,
        controls=tag_rows,
    )

    # ---------------- 个人品味 ----------------
    bins = [0] * 20
    for rating in ratings:
        bins[min(19, rating // 5)] += 1
    bin_max = max(bins) or 1
    rating_slot = content_width / 20
    rating_label = FloatingLabel(page)
    rating_slots: list[ft.Control] = []
    rating_bars: list[ft.Container | None] = []
    active_rating: dict[str, ft.Container | None] = {"bar": None}

    def scale_rating(
        target: ft.Container | None,
        on: bool,
    ) -> None:
        if target is None:
            return
        target.scale = HOVER_SCALE_BAR if on else 1.0
        try:
            target.update()
        except Exception:
            pass

    def rating_at(event: ft.ControlEvent) -> int:
        pos = getattr(event, "local_position", None)
        x = float(pos.x) if pos is not None else 0.0
        index = int(x // rating_slot) if rating_slot else 0
        return max(0, min(19, index))

    def show_rating_label(event: ft.ControlEvent) -> None:
        index = rating_at(event)
        start = index * 5
        end = 100 if index == 19 else start + 5
        rating_label.show(
            event,
            f"{range_label(start, end)} · {bins[index]} 部",
        )
        current = active_rating["bar"]
        if current is not None:
            scale_rating(current, False)
        target = (
            rating_bars[index] if index < len(rating_bars) else None
        )
        scale_rating(target, True)
        active_rating["bar"] = target

    def hide_rating_label() -> None:
        current = active_rating["bar"]
        if current is not None:
            scale_rating(current, False)
        active_rating["bar"] = None
        rating_label.hide()

    def rating_entries(
        start: int,
        end: int,
    ) -> tuple[list[tuple[str, int]], dict[str, Record]]:
        """筛选该分段的评分作品，并生成带重名后缀的条目。"""
        valid: list[tuple[Record, int]] = []
        for record in works:
            rating = parse_rating(record.get("rating"))
            if rating is None:
                continue
            if end >= 100:
                if not start <= rating <= 100:
                    continue
            elif not start <= rating < end:
                continue
            valid.append((record, rating))

        anime_counts: dict[str, int] = {}
        for record, _ in valid:
            anime = record_title(record)
            if anime:
                anime_counts[anime] = (
                    anime_counts.get(anime, 0) + 1
                )

        entries: list[tuple[str, int]] = []
        by_label: dict[str, Record] = {}
        for index, (record, rating) in enumerate(valid):
            anime = record_title(record)
            entry = record_entry(record)
            label = anime
            if anime and anime_counts.get(anime, 0) > 1:
                label = f"{anime} · {entry or index}"
            base = label
            suffix = 2
            while label in by_label:
                label = f"{base} #{suffix}"
                suffix += 1
            by_label[label] = record
            entries.append((label, rating))
        return entries, by_label

    def open_rating_range(start: int, end: int) -> None:
        entries, by_label = rating_entries(start, end)
        if not entries:
            return
        range_route = (
            "/statistics/annual/"
            + quote(name, safe="")
            + f"/rating/{start}-{end}"
        )
        if (
            page.views
            and getattr(page.views[-1], "route", "") == range_route
        ):
            return

        def on_bar_click(label: str) -> None:
            record = by_label.get(label)
            if record is not None:
                open_detail(page, records, record, ENTRY)

        def build_range() -> ft.View:
            return build_bar_chart_view(
                page,
                entries,
                max_value=100,
                reverse=False,
                title=f"{name}（{range_label(start, end)}）",
                route=range_route,
                decimals=0,
                on_bar_click=on_bar_click,
                rebuild=build_range,
            )

        push_view(page, build_range())

    for index in range(20):
        start = index * 5
        end = 100 if index == 19 else start + 5
        count = bins[index]
        bar = ft.Container(
            width=max(4.0, rating_slot - 6),
            height=(
                count / bin_max * BAR_HEIGHT
                if count > 0
                else 0
            ),
            bgcolor=accent,
            border_radius=3,
        )
        bar.animate_scale = animation(
            ANIM_BASE_MS,
            ft.AnimationCurve.EASE_OUT,
        )
        bar.scale = 1.0
        rating_bars.append(bar if count > 0 else None)
        if count > 0:
            bar_w = float(bar.width or 0.0)
            bar_h = float(bar.height or 0.0)
            # 命中高度取柱高；短于 1/4 完整高度时才扩大。
            hit_h = max(bar_h, JOURNEY_HEIGHT / 4.0)
            hit_layer = ft.Container(
                width=bar_w,
                height=hit_h,
                bgcolor=ft.Colors.TRANSPARENT,
                on_hover=lambda event, b=bar: hover_bar(b, event),
                on_click=(
                    lambda event, s=start, e=end: open_rating_range(
                        s,
                        e,
                    )
                ),
            )
            bar.bottom = 0.0
            slot_content = ft.Stack(
                width=bar_w,
                height=hit_h,
                controls=[bar, hit_layer],
            )
        else:
            slot_content = ft.Container(
                width=max(4.0, rating_slot - 6),
                height=0,
            )
        rating_slots.append(
            ft.Container(
                width=rating_slot,
                height=JOURNEY_HEIGHT,
                alignment=ft.Alignment.BOTTOM_CENTER,
                tooltip=(
                    f"{range_label(start, end)} · {count} 部"
                    if count > 0
                    else None
                ),
                content=slot_content,
            )
        )

    if ratings:
        rating_bars_block: list[ft.Control] = [
            ft.GestureDetector(
                on_long_press_start=show_rating_label,
                on_long_press_move_update=show_rating_label,
                on_long_press_end=hide_rating_label,
                on_long_press_cancel=hide_rating_label,
                content=ft.Row(
                    width=content_width,
                    height=JOURNEY_HEIGHT,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    controls=rating_slots,
                ),
            ),
            ft.Row(
                width=content_width,
                spacing=0,
                controls=[
                    ft.Container(
                        width=rating_slot,
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
            ),
        ]
    else:
        rating_bars_block = [
            ft.Row(
                width=content_width,
                controls=[
                    ui_text("暂无数据", size=12, color=secondary)
                ],
            )
        ]
    ratings_block = ft.Column(
        width=content_width,
        spacing=2,
        controls=rating_bars_block,
    )

    # ---------------- 轻松总结 ----------------
    def ai_summary() -> str:
        count = len(works)
        if count == 0:
            if year is None:
                return "这些年还没有补完记录。"
            return "这一年还没有补完记录。"
        scope = "今年" if year is not None else "这些年"
        rng = random.Random(year if year is not None else 0)
        lines = [
            f"{scope}你补完了 {count} 部，总共 {episodes_text}。"
        ]
        if mean is not None and best_score is not None:
            best_title = (
                record_title(best_record) if best_record else ""
            )
            lines.append(
                f"平均 {mean:.1f} 分，最高是"
                f"《{best_title or '未知作品'}》{best_score} 分。"
            )
        if top_tags and tagged_total > 0:
            tag, tag_count = top_tags[0]
            top_share = tag_count / tagged_total
            if top_share >= 0.4:
                lines.append(
                    f"其中 {tag_count} 部带「{tag}」标签，"
                    f"你是不折不扣的{tag}爱好者。"
                )
            elif top_share >= 0.25:
                lines.append(
                    f"「{tag}」出现最多，"
                    f"看来{scope}偏爱这个方向。"
                )
        peak_count = max(month_counts.values())
        mean_month = count / 12
        if peak_count > 0 and peak_count >= mean_month * 2:
            peak_month = max(
                month_counts,
                key=lambda month: month_counts[month],
            )
            lines.append(
                rng.choice(
                    [
                        f"{peak_month} 月是你的爆发期，"
                        f"一个月补完了 {peak_count} 部。",
                        f"{peak_month} 月手感最热，"
                        f"一口气补完了 {peak_count} 部。",
                    ]
                )
            )
        if mean is not None:
            if mean >= 80:
                lines.append(
                    "整体打分相当宽容，几乎看什么都开心。"
                )
            elif mean <= 65:
                lines.append("打分挺严格，能上 75 的都不多。")
        return "\n".join(lines)

    summary_box = ft.Container(
        width=content_width,
        padding=12,
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.05, fg),
        content=ui_text(
            ai_summary(),
            size=12,
            color=secondary,
        ),
    )

    # ---------------- 组装 ----------------
    content: list[ft.Control] = [
        section("概览"),
        kpi_block,
        section("每月酬勤"),
        monthly_block,
        section("最爱标签"),
        tags_block,
        section("个人品味"),
        ratings_block,
        section("轻松总结"),
        summary_box,
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
    return _back_view(
        page,
        route=route,
        title=f"年度报告（{name}）",
        controls=[vertical_page([centered], stretch=True)],
        rebuild=lambda: annual_report_view(page, name),
    )


def open_annual_report(page: ft.Page, name: str) -> None:
    """打开年度报告模板页。"""
    value = str(name or "").strip()
    if not value:
        return
    route = "/statistics/annual/" + quote(value, safe="")
    if page.views and getattr(page.views[-1], "route", "") == route:
        return
    push_view(page, annual_report_view(page, value))
