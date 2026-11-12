"""纪录页。"""

from __future__ import annotations

import datetime as dt
import flet as ft
from bangumi.data.preferences import (
    Preferences,
)
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
from bangumi.views.widgets.stat_card import stat_card
from bangumi.data.quarter_core import (
    earliest_broadcast_date,
)
from bangumi.data.watched_data import (
    is_tv_specification,
    load_records,
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

    rows: list[tuple[str, str]] = [
        ("最喜欢的年份", year_value),
        ("最喜欢的季度", season_value),
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

    def card(title: str, value: str, accent: str) -> ft.Control:
        return stat_card(
            page,
            title,
            value,
            accent=accent,
            expand=None,
            layout="column",
        )

    controls: list[ft.Control] = [
        card(title, value, accents[index % len(accents)])
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


