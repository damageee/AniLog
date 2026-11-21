"""声优代表角色横条竞赛页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data import prework
from bangumi.data.watched_data import Record
from bangumi.views.general.bar_chart import build_bar_chart_view
from bangumi.views.navigation import ENTRY, open_detail, push_view
from .data import role_record


def open_cast_roles_repr(
    page: ft.Page,
    records: list[Record],
    cast: str,
) -> None:
    """打开该声优全部代表角色的横条竞赛页。"""
    index = prework.ensure_index(records)
    roles = list(
        index.roles.get(prework._normalize_name(cast), ())
    )
    labels = [
        f"《{role.entry}》——{role.character}" for role in roles
    ]
    role_by_label = dict(zip(labels, roles))
    title = f"{cast}（代表角色）"
    route = (
        "/statistics/cast/homepage/"
        + quote(cast, safe="")
        + "/roles"
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
