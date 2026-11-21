"""纪录页。"""

from __future__ import annotations

import datetime as dt
from typing import Callable

import flet as ft
from bangumi.data.preferences import (
    Preferences,
)
from bangumi.data.ratings import parse_rating
from bangumi.data.sorting import sort_records_by_broadcast
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.feedback import (
    no_records_note,
)
from bangumi.ui.layout import (
    vertical_page,
)
from bangumi.views.general.bar_chart import build_bar_chart_view
from bangumi.views.navigation import ENTRY, open_detail, push_view
from bangumi.views.templates.list_page import (
    build_list_view,
    open_list_page,
)
from bangumi.views.widgets.stat_card import stat_card
from bangumi.data.quarter_core import (
    earliest_broadcast_date,
)
from bangumi.data.watched_data import (
    Record,
    is_tv_specification,
    load_records,
    record_title,
    split_tags,
)
from bangumi.data.statistics.constants import SEASONS
from bangumi.data.statistics.journey import _completion_date
from bangumi.data.statistics.broadcast import _season_of
from bangumi.data.statistics.records import _spec_episodes
from bangumi.data.statistics.tags import tag_statistics
from bangumi.views.statistics.common.shared import (
    _CARD_COLORS,
    _accent,
    _back_view,
)


def records_view(page: ft.Page) -> ft.View:
    records = load_records()
    preferences = Preferences.load()
    special_dates: set[dt.date] = set()
    for value in preferences.special_completion_dates:
        try:
            special_dates.add(dt.date.fromisoformat(value))
        except ValueError:
            continue
    fg = foreground_color(page)
    accents = [
        _accent(page, light, dark)
        for light, dark in _CARD_COLORS
    ]

    entries: list[tuple[dt.date, int]] = []
    for record in records:
        completion = _completion_date(
            str(record.get("completion") or "")
        )
        if completion is None:
            continue
        if completion in special_dates:
            continue
        episodes = _spec_episodes(
            str(record.get("specification") or "")
        )[1]
        entries.append((completion, episodes))

    if not entries:
        return _back_view(
            page,
            route="/statistics/records",
            rebuild=lambda: records_view(page),
            title="纪录",
            controls=[
                vertical_page(
                    [
                        no_records_note(
                            page,
                            height=60,
                            width=max(
                                200.0,
                                float(page.width or 1000) - 48,
                            ),
                        )
                    ]
                )
            ],
        )

    year_counts: dict[int, int] = {}
    season_counts: dict[str, int] = {}
    quarter_counts: dict[tuple[int, str], int] = {}
    for record in records:
        broadcast = str(record.get("broadcast") or "")
        start = earliest_broadcast_date(broadcast)
        if start is None:
            continue
        year, month, _ = start
        year_counts[year] = year_counts.get(year, 0) + 1
        if "~" not in broadcast and "～" not in broadcast:
            continue
        if not is_tv_specification(
            str(record.get("specification") or "")
        ):
            continue
        season = _season_of(month)
        season_counts[season] = season_counts.get(season, 0) + 1
        quarter_key = (year, season)
        quarter_counts[quarter_key] = (
            quarter_counts.get(quarter_key, 0) + 1
        )

    month_counts: dict[tuple[int, int], int] = {}
    month_episodes: dict[tuple[int, int], int] = {}
    day_counts: dict[dt.date, int] = {}
    day_episodes: dict[dt.date, int] = {}
    for date, episodes in entries:
        month_key = (date.year, date.month)
        month_counts[month_key] = month_counts.get(month_key, 0) + 1
        month_episodes[month_key] = (
            month_episodes.get(month_key, 0) + episodes
        )
        day_counts[date] = day_counts.get(date, 0) + 1
        day_episodes[date] = day_episodes.get(date, 0) + episodes

    season_order = {
        name: index for index, name in enumerate(SEASONS)
    }

    if year_counts:
        best_year = max(
            year_counts.items(),
            key=lambda item: (item[1], item[0]),
        )
        year_value = f"{best_year[0]}（{best_year[1]} 部）"
    else:
        year_value = "—"

    if season_counts:
        best_season = max(
            season_counts.items(),
            key=lambda item: (
                item[1],
                season_order.get(item[0], 0),
            ),
        )
        season_value = (
            f"{best_season[0]}季（{best_season[1]} 部）"
        )
    else:
        season_value = "—"

    if quarter_counts:
        best_quarter = max(
            quarter_counts.items(),
            key=lambda item: (
                item[1],
                item[0][0],
                season_order.get(item[0][1], 0),
            ),
        )
        quarter_value = (
            f"{best_quarter[0][0]} 年"
            f"{best_quarter[0][1]}季（{best_quarter[1]} 部）"
        )
    else:
        quarter_value = "—"

    best_month = max(
        month_counts.items(),
        key=lambda item: (item[1], item[0][0], item[0][1]),
    )
    greediest_month = max(
        month_episodes.items(),
        key=lambda item: (item[1], item[0][0], item[0][1]),
    )
    best_day = max(
        day_counts.items(),
        key=lambda item: (item[1], item[0]),
    )
    most_episodes_day = max(
        day_episodes.items(),
        key=lambda item: (item[1], item[0]),
    )

    tag_rows = [
        (tag, count)
        for tag, count in tag_statistics(records)
        if count > 0
    ]
    tag_rows.sort(key=lambda item: (-item[1], item[0]))
    top_tags = tag_rows[:3]
    if top_tags:
        tag_value = (
            " / ".join(tag for tag, _ in top_tags)
            + "（各 "
            + " / ".join(str(count) for _, count in top_tags)
            + " 次）"
        )
    else:
        tag_value = "—"

    # 统一的作品列表页：rebuild 时重新加载并复用同一筛选逻辑。
    def open_record_list(
        title: str,
        route: str,
        select: Callable[[list[Record]], list[Record]],
    ) -> None:
        def make_entries(
            source: list[Record],
        ) -> list[tuple[str, Record]]:
            ordered = sort_records_by_broadcast(select(source))
            entries: list[tuple[str, Record]] = []
            seen: dict[str, int] = {}
            for record in ordered:
                text = record_title(record)
                if not text:
                    continue
                count = seen.get(text, 0) + 1
                seen[text] = count
                if count > 1:
                    text = f"{text} #{count}"
                entries.append((text, record))
            return entries

        entries = make_entries(records)

        def rebuild() -> ft.View:
            fresh = load_records()
            return build_list_view(
                page,
                title=title,
                route=route,
                entries=make_entries(fresh),
                records=fresh,
                rebuild=rebuild,
            )

        open_list_page(
            page,
            title=title,
            route=route,
            entries=entries,
            records=records,
            rebuild=rebuild,
        )

    def match_year(record: Record, year: int) -> bool:
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        return date is not None and date[0] == year

    def season_broadcast(
        record: Record,
    ) -> tuple[int, str] | None:
        """返回 TV 放送范围起始的 (年份, 季节)。"""
        broadcast = str(record.get("broadcast") or "")
        if "~" not in broadcast and "～" not in broadcast:
            return None
        if not is_tv_specification(
            str(record.get("specification") or "")
        ):
            return None
        date = earliest_broadcast_date(broadcast)
        if date is None:
            return None
        return date[0], _season_of(date[1])

    def match_season(record: Record, season: str) -> bool:
        value = season_broadcast(record)
        return value is not None and value[1] == season

    def match_quarter(
        record: Record,
        target: tuple[int, str],
    ) -> bool:
        return season_broadcast(record) == target

    def match_month(
        record: Record,
        key: tuple[int, int],
    ) -> bool:
        completion = _completion_date(
            str(record.get("completion") or "")
        )
        if completion is None or completion in special_dates:
            return False
        return (completion.year, completion.month) == key

    def match_day(record: Record, day: dt.date) -> bool:
        completion = _completion_date(
            str(record.get("completion") or "")
        )
        return completion == day and completion not in special_dates

    def list_click(
        title: str,
        route: str,
        predicate: Callable[[Record], bool],
    ) -> Callable[[ft.ControlEvent], None]:
        def handler(event: ft.ControlEvent) -> None:
            open_record_list(
                title,
                route,
                lambda source: [
                    record
                    for record in source
                    if predicate(record)
                ],
            )

        return handler

    year_click = (
        list_click(
            f"{best_year[0]} 年",
            f"/statistics/records/year/{best_year[0]}",
            lambda record: match_year(record, best_year[0]),
        )
        if year_counts
        else None
    )
    season_click = (
        list_click(
            f"{best_season[0]}季",
            f"/statistics/records/season/{best_season[0]}",
            lambda record: match_season(record, best_season[0]),
        )
        if season_counts
        else None
    )
    quarter_click = (
        list_click(
            f"{best_quarter[0][0]} 年{best_quarter[0][1]}季",
            (
                f"/statistics/records/quarter/"
                f"{best_quarter[0][0]}/{best_quarter[0][1]}"
            ),
            lambda record: match_quarter(record, best_quarter[0]),
        )
        if quarter_counts
        else None
    )

    month_key = best_month[0]
    month_click = list_click(
        f"{month_key[0]}.{month_key[1]:02d} 补完",
        f"/statistics/records/month/{month_key[0]}-{month_key[1]:02d}",
        lambda record: match_month(record, month_key),
    )
    greedy_key = greediest_month[0]
    greedy_click = list_click(
        f"{greedy_key[0]}.{greedy_key[1]:02d} 补完",
        (
            f"/statistics/records/greedy/"
            f"{greedy_key[0]}-{greedy_key[1]:02d}"
        ),
        lambda record: match_month(record, greedy_key),
    )

    day_date = best_day[0]
    day_click = list_click(
        f"{day_date.strftime('%Y.%m.%d')} 补完",
        f"/statistics/records/day/{day_date.isoformat()}",
        lambda record: match_day(record, day_date),
    )
    binge_date = most_episodes_day[0]
    binge_click = list_click(
        f"{binge_date.strftime('%Y.%m.%d')} 补完",
        f"/statistics/records/binge/{binge_date.isoformat()}",
        lambda record: match_day(record, binge_date),
    )

    tag_click: Callable[[ft.ControlEvent], None] | None = None
    if top_tags:
        tag_set = {tag for tag, _ in top_tags}

        def open_tag_chart(
            event: ft.ControlEvent | None = None,
        ) -> None:
            route_tag = "/statistics/records/tags"
            if (
                page.views
                and getattr(page.views[-1], "route", "") == route_tag
            ):
                return

            def build(source: list[Record]) -> ft.View:
                valid: list[tuple[Record, int]] = []
                for record in source:
                    rating = parse_rating(record.get("rating"))
                    if rating is None:
                        continue
                    if not tag_set & set(
                        split_tags(record.get("tag"))
                    ):
                        continue
                    valid.append((record, rating))
                rating_by_id = {
                    id(record): rating
                    for record, rating in valid
                }
                ordered = sort_records_by_broadcast(
                    [record for record, _ in valid]
                )
                # 先按放送从旧到新，再稳定地按评分降序。
                ordered.sort(
                    key=lambda record: rating_by_id[id(record)],
                    reverse=True,
                )
                arr: list[tuple[str, int]] = []
                by_label: dict[str, Record] = {}
                seen: dict[str, int] = {}
                for record in ordered[:30]:
                    text = record_title(record)
                    if not text:
                        continue
                    count = seen.get(text, 0) + 1
                    seen[text] = count
                    label = (
                        text if count == 1 else f"{text} #{count}"
                    )
                    by_label[label] = record
                    arr.append(
                        (label, rating_by_id[id(record)])
                    )

                def on_bar_click(label: str) -> None:
                    target = by_label.get(label)
                    if target is not None:
                        open_detail(page, source, target, ENTRY)

                return build_bar_chart_view(
                    page,
                    arr,
                    max_value=100,
                    decimals=0,
                    title=" / ".join(
                        tag for tag, _ in top_tags
                    ),
                    route=route_tag,
                    on_bar_click=on_bar_click,
                    rebuild=lambda: build(load_records()),
                )

            push_view(page, build(records))

        tag_click = open_tag_chart

    rows: list[tuple[str, str]] = [
        ("最喜欢的年份", year_value),
        ("最喜欢的季节", season_value),
        (
            "最疯狂的季度",
            quarter_value,
        ),
        (
            "最忙碌的月份",
            f"{best_month[0][0]}.{best_month[0][1]:02d}"
            f"（{best_month[1]} 部）",
        ),
        (
            "最贪婪的月份",
            f"{greediest_month[0][0]}."
            f"{greediest_month[0][1]:02d}"
            f"（{greediest_month[1]} 集）",
        ),
        (
            "单日暴食极致",
            f"{best_day[0].strftime('%Y.%m.%d')}"
            f"（{best_day[1]} 部）",
        ),
        (
            "单日停不下来",
            f"{most_episodes_day[0].strftime('%Y.%m.%d')}"
            f"（{most_episodes_day[1]} 集）",
        ),
        ("最钟情的标签", tag_value),
    ]

    click_handlers: list[
        Callable[[ft.ControlEvent], None] | None
    ] = [
        year_click,
        season_click,
        quarter_click,
        month_click,
        greedy_click,
        day_click,
        binge_click,
        tag_click,
    ]

    def card(
        title: str,
        value: str,
        accent: str,
        on_click: Callable[[ft.ControlEvent], None] | None = None,
    ) -> ft.Control:
        return stat_card(
            page,
            title,
            value,
            accent=accent,
            expand=None,
            layout="column",
            clickable=on_click is not None,
            on_click=on_click,
        )

    controls: list[ft.Control] = [
        card(
            title,
            value,
            accents[index % len(accents)],
            click_handlers[index],
        )
        for index, (title, value) in enumerate(rows)
    ]
    controls.append(
        ui_text(
            "关于统计，视作补完日当天一口气看完了该部作品",
            size=12,
            color=ft.Colors.with_opacity(0.65, fg),
        )
    )
    return _back_view(
        page,
        route="/statistics/records",
        rebuild=lambda: records_view(page),
        title="纪录",
        controls=[
            vertical_page(
                [
                    ft.Column(
                        spacing=10,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.STRETCH
                        ),
                        controls=controls,
                    )
                ]
            )
        ],
    )


