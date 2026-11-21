"""声优某年份角色横条竞赛页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.watched_data import Record
from bangumi.views.general.bar_chart import build_bar_chart_view
from bangumi.views.navigation import ENTRY, open_detail, push_view
from .data import role_record, roles_for_year


def open_cast_year_roles(
    page: ft.Page,
    records: list[Record],
    cast: str,
    year: int,
) -> None:
    """打开该声优指定年份的角色横条竞赛页。"""
    roles = roles_for_year(records, cast, year)
    labels = [
        f"《{role.entry}》——{role.character}" for role in roles
    ]
    role_by_label = dict(zip(labels, roles))
    title = f"{cast}（{year}）"
    route = (
        "/statistics/cast/homepage/"
        + quote(cast, safe="")
        + f"/year/{year}"
    )

    def click(label: str) -> None:
        role = role_by_label.get(label)
        if role is None:
            return
        record = role_record(records, role)
        if record is not None:
            open_detail(page, records, record, ENTRY)

    def build() -> ft.View:
        return build_bar_chart_view(
            page,
            [
                (label, role.score)
                for label, role in zip(labels, roles)
            ],
            title=title,
            route=route,
            decimals=2,
            hide_score=True,
            on_bar_click=click,
            rebuild=build,
        )

    push_view(page, build())
