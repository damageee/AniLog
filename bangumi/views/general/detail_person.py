"""STAFF 人物作品列表页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.ratings import parse_rating
from bangumi.data.sorting import sort_key as name_sort_key
from bangumi.data.watched_data import (
    Record,
    normalize_staff,
    record_title,
    staff_items,
)
from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import hover_link
from bangumi.ui.layout import vertical_page
from bangumi.ui.theme import ui_text
from bangumi.ui.text_metrics import text_width
from bangumi.views.navigation import ENTRY, open_detail, push_view
from bangumi.views.statistics.common.shared import _back_view
from bangumi.views.widgets.toast import copyable_title


def _person_entries(
    records: list[Record],
    person: str,
) -> list[tuple[str, dict]]:
    """统计该人物参与的作品与职务，并按放送/评分/名称排序。"""
    target = str(person or "").strip()
    if not target:
        return []
    merged: dict[str, dict] = {}
    for record in records:
        staff = normalize_staff(record.get("staff"))
        roles: list[str] = []
        for key, value in staff_items(staff):
            parts = [
                part.strip()
                for part in str(value or "").split("、")
            ]
            if target in parts and key not in roles:
                roles.append(key)
        if not roles:
            continue
        anime = record_title(record) or str(
            record.get("anime")
            or record.get("entry")
            or ""
        ).strip()
        if not anime:
            continue
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        rating = parse_rating(record.get("rating")) or 0
        current = merged.get(anime)
        if current is None:
            merged[anime] = {
                "roles": roles,
                "record": record,
                "date": date,
                "rating": rating,
            }
            continue
        for role in roles:
            if role not in current["roles"]:
                current["roles"].append(role)
        if date is not None and (
            current["date"] is None
            or date < current["date"]
        ):
            current["date"] = date
        current["rating"] = max(current["rating"], rating)

    def entry_key(item: tuple[str, dict]) -> tuple:
        anime, info = item
        date = info["date"]
        return (
            1 if date is None else 0,
            date or (0, 0, 0),
            -info["rating"],
            name_sort_key(anime),
        )

    return sorted(merged.items(), key=entry_key)


def build_person_view(
    page: ft.Page,
    records: list[Record],
    person: str,
    route: str,
) -> ft.View:
    """展示某人物参与的作品。"""
    # 延迟导入，避免与 staff_search 的相互引用。
    from .staff_search import open_staff_key_search

    name = str(person or "").strip()
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    entries = _person_entries(records, name)
    # 左右栏宽按内容估算，上限为 1/3 屏宽；1.12 + 24 为测量误差与 padding 余量。
    cap = max(120.0, float(page.width or 1000) / 3.0)
    roles_max = max(
        (
            float(text_width("、".join(info["roles"]), size=14))
            for _, info in entries
        ),
        default=0.0,
    )
    anime_max = max(
        (float(text_width(anime, size=14)) for anime, _ in entries),
        default=0.0,
    )
    left_w = min(roles_max * 1.12 + 24.0, cap)
    right_w = min(anime_max * 1.12 + 24.0, cap)
    left_boxes: list[ft.Container] = []
    right_boxes: list[ft.Container] = []
    rows: list[ft.Control] = []
    for anime, info in entries:
        roles_text = "、".join(info["roles"])
        record = info["record"]
        # 职务按「、」拆开，每段独立 hover 与点击，打开该职务的人物搜索。
        role_parts = [
            part.strip()
            for part in roles_text.split("、")
            if part.strip()
        ]
        role_controls: list[ft.Control] = []
        for index, part in enumerate(role_parts):
            if index:
                role_controls.append(ui_text("、", size=14, color=fg))
            role_controls.append(
                hover_link(
                    page,
                    ui_text(part, size=14, color=fg),
                    fg,
                    lambda event, k=part: open_staff_key_search(
                        page,
                        records,
                        k,
                    ),
                )
            )
        left_content = ft.Row(
            wrap=True,
            spacing=0,
            run_spacing=2,
            alignment=ft.MainAxisAlignment.END,
            controls=role_controls,
        )
        # 左栏右对齐，宽度取内容宽度；超长自动换行。
        left_box = ft.Container(
            width=left_w,
            alignment=ft.Alignment.CENTER_RIGHT,
            padding=ft.Padding.only(right=12),
            content=left_content,
        )
        # 右栏左对齐，宽度取内容宽度；超长自动换行。
        right_box = ft.Container(
            width=right_w,
            alignment=ft.Alignment.CENTER_LEFT,
            padding=ft.Padding.only(left=12),
            content=hover_link(
                page,
                ui_text(anime, size=14, color=fg),
                fg,
                lambda event, r=record: open_detail(
                    page,
                    records,
                    r,
                    ENTRY,
                ),
            ),
        )
        left_boxes.append(left_box)
        right_boxes.append(right_box)
        rows.append(
            ft.Row(
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    left_box,
                    ft.Container(
                        width=1,
                        height=20,
                        bgcolor=ft.Colors.with_opacity(0.25, fg),
                    ),
                    right_box,
                ],
            )
        )
    if not rows:
        rows = [ui_text("暂无数据", size=12, color=secondary)]

    width_state = {"left": left_w, "right": right_w}

    def on_resize(event=None) -> None:
        # 仅栈顶响应；按 1/3 屏宽上限重算左右栏宽。
        if (
            not page.views
            or str(getattr(page.views[-1], "route", "")) != route
        ):
            return
        cap = max(120.0, float(page.width or 1000) / 3.0)
        left = min(roles_max * 1.12 + 24.0, cap)
        right = min(anime_max * 1.12 + 24.0, cap)
        if (
            abs(left - width_state["left"]) < 1
            and abs(right - width_state["right"]) < 1
        ):
            return
        width_state["left"] = left
        width_state["right"] = right
        for box in left_boxes:
            box.width = left
        for box in right_boxes:
            box.width = right
        try:
            page.update()
        except Exception:
            pass
    column = ft.Column(spacing=6, controls=rows)
    # 整块按内容宽度收缩后水平居中，竖线跟随左侧内容宽度。
    centered = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[column],
    )
    view = _back_view(
        page,
        route=route,
        title=name or "STAFF",
        controls=[vertical_page([centered], stretch=True)],
        rebuild=lambda: build_person_view(
            page,
            records,
            name,
            route,
        ),
    )
    if view.appbar is not None:
        view.appbar.title = copyable_title(page, name or "STAFF")
    # 只读页面：返回时无需重建下层页面。
    data = view.data if isinstance(view.data, dict) else {}
    data["skip_prev_refresh"] = True
    data["no_compact_rebuild"] = True
    view.data = data
    # 全局 dispatcher 已带 120ms 防抖，这里只注册，不再自行防抖。
    from bangumi.views.navigation.stack import register_resize_handler

    register_resize_handler(page, route, on_resize)
    return view


def open_person_page(
    page: ft.Page,
    records: list[Record],
    person: str,
) -> None:
    """打开某 STAFF 人物的作品列表。"""
    name = str(person or "").strip()
    if not name:
        return
    route = f"/watched/person/{quote(name, safe='')}"
    if (
        page.views
        and str(getattr(page.views[-1], "route", "")) == route
    ):
        return
    push_view(page, build_person_view(page, records, name, route))
