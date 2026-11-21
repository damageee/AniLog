"""两位声优的代表角色共演对比页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.watched_data import Record
from bangumi.views.general.bar_compare import build_bar_compare_view
from bangumi.views.navigation import ENTRY, open_detail, push_view
from .data import role_record, series_roles

__all__ = ["open_cast_roles_cowork"]


def open_cast_roles_cowork(
    page: ft.Page,
    records: list[Record],
    cast_a: str,
    cast_b: str,
    *,
    hide_score: bool = False,
) -> None:
    """打开两位声优的系列角色共演对比页。"""
    a_rows = series_roles(records, cast_a)
    b_rows = series_roles(records, cast_b)
    b_map = {
        series: (names, score, role)
        for series, names, score, role in b_rows
    }

    def label(series: str, names: list[str]) -> str:
        text = "、".join(names) if names else "—"
        return f"《{series}》——{text}"

    shared: list[
        tuple[
            str,
            list[str],
            float,
            object,
            list[str],
            float,
            object,
        ]
    ] = []
    for series, a_names, a_score, a_role in a_rows:
        item = b_map.get(series)
        if item is None:
            continue
        b_names, b_score, b_role = item
        shared.append(
            (
                series,
                a_names,
                a_score,
                a_role,
                b_names,
                b_score,
                b_role,
            )
        )

    scores = (
        [row[2] for row in shared]
        + [row[5] for row in shared]
    )
    score_max = max(scores) if scores else 0.0
    if score_max <= 0:
        score_max = 1.0
    arr_l = [
        (label(series, a_names), a_score, score_max)
        for series, a_names, a_score, _ar, _bn, _bs, _br in shared
    ]
    arr_r = [
        (label(series, b_names), b_score, score_max)
        for series, _an, _as, _ar, b_names, b_score, _br in shared
    ]
    left_roles = {
        label(series, a_names): a_role
        for series, a_names, _as, a_role, _bn, _bs, _br in shared
    }
    right_roles = {
        label(series, b_names): b_role
        for series, _an, _as, _ar, b_names, _bs, b_role in shared
    }

    def open_role(role) -> None:
        if role is None:
            return
        record = role_record(records, role)
        if record is not None:
            open_detail(page, records, record, ENTRY)

    def click_l(text: str) -> None:
        open_role(left_roles.get(text))

    def click_r(text: str) -> None:
        open_role(right_roles.get(text))

    title = f"{cast_a} × {cast_b}"
    route = (
        "/statistics/cast/homepage/"
        + quote(cast_a, safe="")
        + "/cowork/"
        + quote(cast_b, safe="")
    )

    def build() -> ft.View:
        return build_bar_compare_view(
            page,
            cast_a,
            arr_l,
            cast_b,
            arr_r,
            title=title,
            route=route,
            decimals=2,
            hide_score=hide_score,
            on_bar_click_l=click_l,
            on_bar_click_r=click_r,
            rebuild=build,
        )

    push_view(page, build())
