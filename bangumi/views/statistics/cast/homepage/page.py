"""声优统计主页。"""

from __future__ import annotations

from urllib.parse import quote

import flet as ft

from bangumi.data import prework
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import Record
from bangumi.data.statistics.constants import SEASONS
from bangumi.ui.anim import animation
from bangumi.ui.colors import foreground_color
from bangumi.ui.constants import ANIM_BASE_MS, HOVER_SCALE_BAR
from bangumi.ui.events import is_hover
from bangumi.ui.interaction import FloatingLabel, hover_copy, hover_link
from bangumi.ui.layout import vertical_page
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import CAST, ENTRY, open_detail, push_view
from bangumi.views.statistics.common.shared import _accent, _back_view
from bangumi.views.widgets.stat_card import stat_card
from bangumi.views.widgets.toast import copyable_title
from bangumi.views.widgets.links import copy_text

from .data import cast_works, role_record
from .roles_repr import open_cast_roles_repr
from .roles_cowork import open_cast_roles_cowork
from .roles_year import open_cast_year_roles


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


def _list_row(
    page: ft.Page,
    index: int,
    name: str,
    on_click,
    *,
    entry: str = "",
    on_entry_click=None,
) -> ft.Control:
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    if entry:
        content: ft.Control = ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                hover_copy(
                    page,
                    ui_text(name, size=14, color=fg),
                    lambda event: page.run_task(
                        copy_text,
                        page,
                        name,
                        "已复制角色名到剪贴板",
                    ),
                ),
                ui_text(" · ", size=14, color=secondary),
                hover_link(
                    page,
                    ui_text(entry, size=14, color=fg),
                    fg,
                    on_entry_click,
                ),
            ],
        )
    else:
        content = hover_link(
            page,
            ui_text(name, size=14, color=fg),
            fg,
            on_click,
        )
    return ft.Container(
        content=ft.Row(
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
                    content=content,
                ),
            ],
        ),
    )


def _cowork_row(
    page: ft.Page,
    index: int,
    name: str,
    count: int,
    on_name_click,
    on_count_click,
) -> ft.Control:
    """共演行：姓名与次数分别可点。"""
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    return ft.Container(
        content=ft.Row(
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
                    content=ft.Row(
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            hover_link(
                                page,
                                ui_text(
                                    name,
                                    size=14,
                                    color=fg,
                                    no_wrap=True,
                                ),
                                fg,
                                on_name_click,
                            ),
                            ui_text(" (", size=14, color=fg, no_wrap=True),
                            hover_link(
                                page,
                                ui_text(
                                    str(count),
                                    size=14,
                                    color=fg,
                                    no_wrap=True,
                                ),
                                fg,
                                on_count_click,
                            ),
                            ui_text(")", size=14, color=fg, no_wrap=True),
                        ],
                    ),
                ),
            ],
        ),
    )


def _cast_homepage_view(
    page: ft.Page,
    records: list[Record],
    cast: str,
) -> ft.View:
    route = "/statistics/cast/homepage/" + quote(cast, safe="")
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    accent = _accent(page, "#2563EB", "#60A5FA")
    available = fit_chart_width(page, 1000.0, min_width=280.0)
    content_width = min(available, 520.0)
    narrow = is_compact_layout(page)

    index = prework.ensure_index(records)
    cast_key = prework._normalize_name(cast)
    roles = list(index.roles.get(cast_key, ()))
    work_rows = cast_works(records, cast)
    works = [record for record, _names in work_rows]

    years: set[int] = set()
    quarters: set[tuple[int, int]] = set()
    quarter_counts: dict[tuple[int, int], int] = {}
    for record, _names in work_rows:
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        if date is None:
            continue
        years.add(date[0])
        key = (date[0], (date[1] - 1) // 3 + 1)
        quarters.add(key)
        quarter_counts[key] = quarter_counts.get(key, 0) + 1

    span = (
        "—"
        if not years
        else f"{min(years)}-{max(years)}"
    )
    sample_record = (
        works[0] if works else (records[0] if records else None)
    )

    def open_all_roles(event: ft.ControlEvent) -> None:
        if sample_record is None:
            return
        open_detail(
            page,
            records,
            {**sample_record, "cast": cast},
            CAST,
        )

    buttons = ft.Row(
        width=content_width,
        spacing=12,
        controls=[
            ft.Container(
                expand=1,
                content=ft.Button(
                    content=ui_text("全部角色", size=15),
                    height=44,
                    on_click=open_all_roles,
                    disabled=sample_record is None,
                ),
            ),
            ft.Container(
                expand=1,
                content=ft.Button(
                    content=ui_text("代表角色", size=15),
                    height=44,
                    on_click=lambda event: open_cast_roles_repr(
                        page, records, cast
                    ),
                    disabled=not roles,
                ),
            ),
        ],
    )

    def card(title: str, value: str) -> ft.Control:
        return stat_card(
            page,
            title,
            value,
            accent=accent,
            expand=1,
        )

    items = [
        ("作品数", f"{len(works)} 部"),
        ("角色数", f"{len(roles)} 个"),
        ("活跃年数", f"{len(years)} 年"),
        ("活跃季度", f"{len(quarters)} 季"),
        ("活跃年份跨度", span),
    ]
    if narrow:
        kpi_rows = [
            ft.Row(spacing=12, controls=[card(title, value)])
            for title, value in items
        ]
    else:
        kpi_rows = [
            ft.Row(
                spacing=12,
                controls=[
                    card("作品数", f"{len(works)} 部"),
                    card("角色数", f"{len(roles)} 个"),
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[
                    card("活跃年数", f"{len(years)} 年"),
                    card("活跃季度", f"{len(quarters)} 季"),
                ],
            ),
            ft.Row(
                spacing=12,
                controls=[card("活跃年份跨度", span)],
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

    if years:
        first_year = min(years)
        last_year = max(years)
        max_count = max(quarter_counts.values(), default=0) or 1
        label_w = 58.0
        gap = 4.0
        cell = max(
            10.0,
            (content_width - label_w - 8.0 - gap * 11) / 12,
        )
        heat_label = FloatingLabel(page)
        heat_cells: dict[tuple[int, int], ft.Container] = {}
        active_heat: dict[str, ft.Container | None] = {"bar": None}

        def _heat_hover(
            target: ft.Container,
            event: ft.ControlEvent,
        ) -> None:
            target.scale = HOVER_SCALE_BAR if is_hover(event) else 1.0
            try:
                target.update()
            except Exception:
                pass

        def scale_heat(
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

        row_starts = list(
            range(first_year, last_year + 1, 3)
        )

        def heat_target(
            event: ft.ControlEvent,
        ) -> tuple[int, int, ft.Container] | None:
            pos = getattr(event, "local_position", None)
            if pos is None:
                return None
            step = cell + gap
            col = int(float(pos.x) // step) if step else 0
            row = int(float(pos.y) // step) if step else 0
            col = max(0, min(11, col))
            row = max(0, min(len(row_starts) - 1, row))
            year = first_year + row * 3 + col // 4
            if year > last_year:
                return None
            quarter = col % 4 + 1
            target = heat_cells.get((year, quarter))
            if target is None:
                return None
            return year, quarter, target

        def show_heat(event: ft.ControlEvent) -> None:
            item = heat_target(event)
            if item is None:
                return
            year, quarter, target = item
            count = quarter_counts.get((year, quarter), 0)
            heat_label.show(
                event,
                f"{year} {SEASONS[quarter - 1]} · {count} 部",
            )
            scale_heat(active_heat["bar"], False)
            scale_heat(target, True)
            active_heat["bar"] = target

        def end_heat(event: ft.ControlEvent) -> None:
            scale_heat(active_heat["bar"], False)
            active_heat["bar"] = None
            heat_label.hide()

        label_rows: list[ft.Control] = []
        cell_rows: list[ft.Control] = []
        for start in row_starts:
            end = min(start + 2, last_year)
            label_rows.append(
                ft.Container(
                    width=label_w,
                    height=cell,
                    alignment=ft.Alignment.CENTER_RIGHT,
                    content=ui_text(
                        f"{start}-{end}" if end != start else str(start),
                        size=10,
                        color=secondary,
                        no_wrap=True,
                    ),
                )
            )
            cells: list[ft.Control] = []
            for offset in range(12):
                year = start + offset // 4
                quarter = offset % 4 + 1
                if year > last_year:
                    cells.append(
                        ft.Container(width=cell, height=cell)
                    )
                    continue
                count = quarter_counts.get((year, quarter), 0)
                ratio = count / max_count
                color = (
                    ft.Colors.with_opacity(0.08, fg)
                    if count <= 0
                    else ft.Colors.with_opacity(
                        0.15 + 0.85 * ratio,
                        accent,
                    )
                )
                cell_container = ft.Container(
                    width=cell,
                    height=cell,
                    border_radius=3,
                    bgcolor=color,
                    tooltip=(
                        f"{year} {SEASONS[quarter - 1]}"
                        f" · {count} 部"
                    ),
                    on_click=(
                        lambda event, y=year: open_cast_year_roles(
                            page, records, cast, y
                        )
                    ),
                    animate_scale=animation(
                        ANIM_BASE_MS,
                        ft.AnimationCurve.EASE_OUT,
                    ),
                    scale=1.0,
                )
                cell_container.on_hover = (
                    lambda event, c=cell_container: _heat_hover(c, event)
                )
                heat_cells[(year, quarter)] = cell_container
                cells.append(cell_container)
            cell_row = ft.Row(spacing=gap, controls=cells)
            cell_rows.append(cell_row)

        cells_column = ft.Column(
            spacing=gap,
            controls=cell_rows,
        )
        cells_gesture = ft.GestureDetector(
            on_long_press_start=show_heat,
            on_long_press_move_update=show_heat,
            on_long_press_end=end_heat,
            on_long_press_cancel=end_heat,
            content=cells_column,
        )
        distribution: ft.Control = ft.Row(
            width=content_width,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column(spacing=gap, controls=label_rows),
                cells_gesture,
            ],
        )
    else:
        distribution = ui_text(
            "暂无放送年份数据",
            size=12,
            color=secondary,
        )

    cowork_rows: list[ft.Control] = []
    for position, (name, count) in enumerate(
        prework.cowork_neighbors(cast)[:5],
        start=1,
    ):
        cowork_rows.append(
            _cowork_row(
                page,
                position,
                name,
                count,
                lambda event, value=name: open_cast_homepage(
                    page, records, value
                ),
                lambda event, value=name: open_cast_roles_cowork(
                    page, records, cast, value, hide_score=True
                ),
            )
        )

    role_rows: list[ft.Control] = []
    for position, role in enumerate(roles[:3], start=1):
        role_rows.append(
            _list_row(
                page,
                position,
                role.character,
                None,
                entry=role.entry,
                on_entry_click=lambda event, r=role: _open_role(
                    page, records, r
                ),
            )
        )

    cowork_block = ft.Column(
        width=content_width,
        spacing=6,
        controls=(
            cowork_rows
            or [ui_text("暂无共演数据", size=12, color=secondary)]
        ),
    )
    role_block = ft.Column(
        width=content_width,
        spacing=6,
        controls=(
            role_rows
            or [ui_text("暂无角色数据", size=12, color=secondary)]
        ),
    )

    content = ft.Column(
        width=content_width,
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            buttons,
            kpi_block,
            _section_title(page, "活跃状态", content_width),
            distribution,
            _section_title(page, "共演次数", content_width),
            cowork_block,
            _section_title(page, "代表角色", content_width),
            role_block,
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
        ],
    )

    page_width = max(320.0, float(page.width or 1000) - 48.0)
    centered = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
        width=page_width,
        controls=[content],
    )

    view = _back_view(
        page,
        route=route,
        title=cast,
        controls=[vertical_page([centered], stretch=True)],
        rebuild=lambda: _cast_homepage_view(page, records, cast),
    )
    if view.appbar is not None:
        view.appbar.title = copyable_title(page, cast)
    return view


def _open_role(
    page: ft.Page,
    records: list[Record],
    role: prework.RoleScore,
) -> None:
    record = role_record(records, role)
    if record is not None:
        open_detail(page, records, record, ENTRY)


def open_cast_homepage(
    page: ft.Page,
    records: list[Record],
    cast: str,
) -> None:
    """打开声优统计主页。"""
    name = str(cast or "").strip()
    if not name:
        return
    view = _cast_homepage_view(page, records, name)
    if page.views and getattr(page.views[-1], "route", "") == view.route:
        return
    push_view(page, view)
