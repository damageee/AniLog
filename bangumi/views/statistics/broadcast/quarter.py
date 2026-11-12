"""季度与年×季度统计页。"""

from __future__ import annotations

import asyncio
import random
import time
from typing import (
    Callable,
)
import flet as ft
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.interaction import (
    back_icon,
)
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.views.navigation import (
    go_back,
    push_view,
)
from bangumi.ui.layout import (
    scroll_page,
)
from .year_quarter import (
    build_quarter_view,
)
from bangumi.views.general.detail_quarter_works import (
    build_quarter_works_view,
)
from bangumi.data.watched_data import (
    load_records,
)
from bangumi.data.quarter_core import (
    quarter_label,
)
from bangumi.data.statistics.constants import SEASONS
from bangumi.data.statistics.broadcast import broadcast_data
from bangumi.ui.events import event_position
from bangumi.ui import scroll_memory
from bangumi.views.statistics.common.overlays import (
    QUOTES,
    _OverlayLayers,
    _hide_page_overlay,
    _install_overlay_hook,
    _overlay_placement,
    _quote_overlay,
    _register_overlay,
)
from bangumi.views.statistics.common.shared import (
    HEAT_SIZE,
    ANIMATION_SECONDS,
    _accent,
    _back_view,
    _is_desktop_platform,
    _no_records_note,
)
from bangumi.ui.heat_zoom import (
    animate_heat_cells,
    attach_heat_zoom,
    reset_heat_zoom,
)
from bangumi.ui.anim import animation, entry_animations_enabled
from bangumi.ui.page_state import first_entry, mark_seen


HIDE_DELAY = 0.05


def _heat_cell(
    page: ft.Page,
    *,
    label: str,
    count: int,
    ratio: float,
    accent: str,
    summary: bool,
    desktop: bool,
    on_show: Callable[[ft.ControlEvent], None],
    on_hide: Callable[[ft.ControlEvent], None],
    on_open: Callable[[ft.ControlEvent], None],
    on_long_start: Callable[[ft.ControlEvent], None] | None = None,
    on_long_move: Callable[[ft.ControlEvent], None] | None = None,
    on_long_end: Callable[[ft.ControlEvent], None] | None = None,
    heat_cells: list[ft.Container] | None = None,
    animate: bool = True,
) -> ft.Control:
    fg = foreground_color(page)
    if summary:
        bgcolor = ft.Colors.with_opacity(0.16, accent)
        text_color = fg
    elif count <= 0:
        bgcolor = background_color(page)
        text_color = ft.Colors.with_opacity(0.55, fg)
    else:
        bgcolor = ft.Colors.with_opacity(
            0.12 + 0.78 * ratio,
            accent,
        )
        text_color = (
            ft.Colors.WHITE if ratio >= 0.45 else fg
        )
    if count <= 0 and not summary:
        border_color = ft.Colors.with_opacity(0.16, fg)
    else:
        border_color = ft.Colors.with_opacity(
            0.35 if summary else 0.12,
            accent,
        )
    cell = ft.Container(
        width=HEAT_SIZE,
        height=HEAT_SIZE,
        alignment=ft.Alignment.CENTER,
        border_radius=6,
        bgcolor=bgcolor,
        border=ft.Border.all(
            1,
            border_color,
        ),
        content=ui_text(
            str(count),
            size=12,
            weight=(
                ft.FontWeight.BOLD if summary else ft.FontWeight.NORMAL
            ),
            color=text_color,
            text_align=ft.TextAlign.CENTER,
        ),
        opacity=0 if animate else 1,
        scale=ft.Scale(1.4 if animate else 1.0),
        animate_opacity=(
            animation(220)
            if animate
            else None
        ),
        animate_scale=(
            animation(220)
            if animate
            else None
        ),
    )
    attach_heat_zoom(
        page,
        cell,
        target=1.2,
        on_tap=on_show,
        initial_scale=1.4 if animate else 1.0,
    )
    if heat_cells is not None:
        heat_cells.append(cell)

    def enter(event: ft.ControlEvent) -> None:
        on_show(event)

    def leave(event: ft.ControlEvent) -> None:
        on_hide(event)

    return ft.GestureDetector(
        width=HEAT_SIZE,
        height=HEAT_SIZE,
        on_enter=enter,
        on_exit=leave,
        on_tap=on_open,
        on_long_press_start=on_long_start,
        on_long_press_move_update=on_long_move,
        on_long_press_end=on_long_end,
        on_long_press_cancel=on_long_end,
        content=cell,
    )


def quarter_view(page: ft.Page) -> ft.View:
    route = "/statistics/broadcast/quarter"
    animate = entry_animations_enabled() and first_entry(page, route)
    if animate:
        mark_seen(page, route)
    data = broadcast_data(ranges_only=True)
    accent = _accent(page, "#2563EB", "#60A5FA")
    fg = foreground_color(page)
    desktop = _is_desktop_platform(page)
    overlay = _OverlayLayers(page)
    _register_overlay(page, overlay)
    _install_overlay_hook(page)

    label_text = ui_text("", size=12, color=fg)
    label = ft.Container(
        width=180,
        height=34,
        alignment=ft.Alignment.CENTER,
        ignore_interactions=True,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=8,
        bgcolor=background_color(page),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(0.25, accent),
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(2, 4),
        ),
        content=label_text,
    )
    state: dict[str, ft.Container | None] = {
        "quote": None,
        "panel": None,
    }
    active_cell: dict[
        str,
        tuple[int | None, str] | None,
    ] = {"cell": None}
    last_show: dict[str, float] = {"time": 0.0}
    hide_token = {"value": 0}

    def remove_quote() -> None:
        current = state["quote"]
        state["quote"] = None
        if current is not None:
            overlay.remove(current)

    def clear_layers() -> None:
        active_cell["cell"] = None
        overlay.remove(label)
        remove_quote()

    def open_quarter(year: int | None, season: str) -> None:
        if year is None:
            title = f"全部{season}季度"
            route = f"/statistics/broadcast/quarter/all/{season}"
            records = data.season_totals[season]
        else:
            title = quarter_label(year, SEASONS.index(season))
            route = f"/statistics/broadcast/quarter/{year}/{season}"
            records = data.matrix[(year, season)]

        def do_rebuild() -> ft.View:
            return build_quarter_works_view(
                page,
                load_records(),
                {},
                route,
                title=title,
                selected=records,
                before=lambda: _hide_page_overlay(page),
            )

        view = build_quarter_works_view(
            page,
            load_records(),
            {},
            route,
            title=title,
            selected=records,
            before=lambda: _hide_page_overlay(page),
            rebuild=do_rebuild,
        )
        if view is not None:
            push_view(page, view)

    def show_cell(
        event: ft.ControlEvent,
        *,
        year: int | None,
        season: str,
        count: int,
    ) -> None:
        if view not in page.views or page.views[-1] is not view:
            return
        hide_token["value"] += 1
        x, y = event_position(event)
        quote_text = random.choice(QUOTES[season])
        quote, quote_h = _quote_overlay(
            page,
            quote_text,
            panel=state.get("panel"),
        )
        state["panel"] = quote
        state["quote"] = quote
        overlay.show(quote)

        pos = _overlay_placement(
            page,
            event,
            width=180,
            height=34,
            bottom_reserve=quote_h + 12,
        )
        active_cell["cell"] = (year, season)
        last_show["time"] = time.monotonic()
        prefix = "全部年份" if year is None else str(year)
        label_text.value = f"{prefix} {season} · {count} 部"
        label.left = pos["left"]
        label.top = pos.get("top")
        label.bottom = pos.get("bottom")
        overlay.show(label)

    def hide_cell(
        event: ft.ControlEvent,
        year: int | None,
        season: str,
    ) -> None:
        hide_token["value"] += 1
        token = hide_token["value"]

        async def clear() -> None:
            await asyncio.sleep(HIDE_DELAY)
            if token != hide_token["value"]:
                return
            if active_cell["cell"] != (year, season):
                return
            active_cell["cell"] = None
            overlay.remove(label)
            remove_quote()

        page.run_task(clear)

    active_long: dict[str, object] = {
        "year": None,
        "season": "",
    }
    cell_map: dict[
        tuple[int | None, str],
        ft.Container,
    ] = {}
    active_heat: dict[str, ft.Container | None] = {"cell": None}

    def scale_heat(
        target: ft.Container | None,
        on: bool,
    ) -> None:
        if target is None:
            return
        target.scale = ft.Scale(1.2 if on else 1.0)
        try:
            target.update()
        except Exception:
            pass

    def show_at(
        event: ft.ControlEvent,
        year: int | None,
        season: str,
    ) -> None:
        count = len(data.matrix[(year, season)])
        show_cell(event, year=year, season=season, count=count)
        current = active_heat["cell"]
        if current is not None:
            scale_heat(current, False)
        target = cell_map.get((year, season))
        scale_heat(target, True)
        active_heat["cell"] = target
        active_long["year"] = year
        active_long["season"] = season

    def move_cell(
        event: ft.ControlEvent,
        year: int | None,
        season: str,
    ) -> None:
        offset = getattr(event, "local_offset_from_origin", None)
        if offset is None:
            offset = getattr(event, "offset_from_origin", None)
        if offset is None:
            return
        dx = float(getattr(offset, "x", 0) or 0)
        dy = float(getattr(offset, "y", 0) or 0)
        col_delta = int(round(dx / (HEAT_SIZE + 4)))
        row_delta = int(round(dy / (HEAT_SIZE + 4)))

        try:
            season_index = SEASONS.index(season)
        except ValueError:
            season_index = 0
        target_season = SEASONS[
            max(0, min(len(SEASONS) - 1, season_index + col_delta))
        ]

        if year is None:
            target_year = None
        else:
            year_list = list(data.range_years)
            try:
                year_index = year_list.index(year)
            except ValueError:
                return
            target_year = year_list[
                max(
                    0,
                    min(
                        len(year_list) - 1,
                        year_index + row_delta,
                    ),
                )
            ]

        show_at(event, target_year, target_season)

    def end_cell(
        event: ft.ControlEvent,
        year: int | None,
        season: str,
    ) -> None:
        active_season = str(active_long["season"] or "")
        active_year = (
            active_long["year"] if active_season else year
        )
        hide_cell(
            event,
            active_year,  # type: ignore[arg-type]
            active_season or season,
        )
        current = active_heat["cell"]
        if current is not None:
            scale_heat(current, False)
        active_heat["cell"] = None
        active_long["season"] = ""

    matrix_width = 52 + 4 * HEAT_SIZE + 4 * 4
    years = data.range_years
    if not years:
        content = ft.GestureDetector(
            expand=True,
            on_tap=lambda event: None,
            content=scroll_page(
                [
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            _no_records_note(
                                page,
                                height=60,
                                width=max(
                                    200.0,
                                    float(page.width or 1000) - 48,
                                ),
                            )
                        ],
                    )
                ],
                spacing=10,
            ),
        )
        return _back_view(
            page,
            route="/statistics/broadcast/quarter",
            rebuild=lambda: quarter_view(page),
            title="季度",
            controls=[content],
        )

    header = ft.Row(
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(width=52),
            *[
                ft.Container(
                    width=HEAT_SIZE,
                    height=24,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        season,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=fg,
                        text_align=ft.TextAlign.CENTER,
                    ),
                )
                for season in SEASONS
            ],
        ],
    )

    rows: list[ft.Control] = [header]
    heat_cells: list[ft.Container] = []
    for year in years:
        cells: list[ft.Control] = [
            ft.Container(
                width=52,
                height=HEAT_SIZE,
                alignment=ft.Alignment.CENTER,
                content=ui_text(
                    str(year),
                    size=11,
                    color=ft.Colors.with_opacity(0.72, fg),
                ),
            )
        ]
        for season in SEASONS:
            count = len(data.matrix[(year, season)])
            ratio = (
                count / data.global_max
                if data.global_max
                else 0.0
            )
            cells.append(
                _heat_cell(
                    page,
                    label=f"{year} {season}",
                    count=count,
                    ratio=ratio,
                    accent=accent,
                    summary=False,
                    desktop=desktop,
                    heat_cells=heat_cells,
                    animate=animate,
                    on_show=(
                        lambda event, y=year, s=season, c=count: (
                            show_cell(
                                event,
                                year=y,
                                season=s,
                                count=c,
                            )
                        )
                    ),
                    on_hide=(
                        lambda event, y=year, s=season: hide_cell(
                            event,
                            y,
                            s,
                        )
                    ),
                    on_open=(
                        lambda event, y=year, s=season: open_quarter(
                            y, s
                        )
                    ),
                    on_long_start=(
                        lambda event, y=year, s=season: show_at(
                            event,
                            y,
                            s,
                        )
                    ),
                    on_long_move=(
                        lambda event, y=year, s=season: move_cell(
                            event,
                            y,
                            s,
                        )
                    ),
                    on_long_end=(
                        lambda event, y=year, s=season: end_cell(
                            event,
                            y,
                            s,
                        )
                    ),
                )
            )
            cell_map[(year, season)] = heat_cells[-1]
        rows.append(
            ft.Row(
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=cells,
            )
        )

    summary_cells: list[ft.Control] = [
        ft.Container(
            width=52,
            height=HEAT_SIZE,
            alignment=ft.Alignment.CENTER,
            content=ui_text(
                "全",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=fg,
            ),
        )
    ]
    for season in SEASONS:
        count = len(data.season_totals[season])
        summary_cells.append(
            _heat_cell(
                page,
                label=f"全部年份 {season}",
                count=count,
                ratio=0.0,
                accent=accent,
                summary=True,
                desktop=desktop,
                heat_cells=heat_cells,
                animate=animate,
                on_show=(
                    lambda event, s=season, c=count: show_cell(
                        event,
                        year=None,
                        season=s,
                        count=c,
                    )
                ),
                on_hide=(
                    lambda event, s=season: hide_cell(
                        event,
                        None,
                        s,
                    )
                ),
                on_open=(
                    lambda event, s=season: open_quarter(None, s)
                ),
                on_long_start=(
                    lambda event, s=season: show_at(
                        event,
                        None,
                        s,
                    )
                ),
                on_long_move=(
                    lambda event, s=season: move_cell(
                        event,
                        None,
                        s,
                    )
                ),
                on_long_end=(
                    lambda event, s=season: end_cell(
                        event,
                        None,
                        s,
                    )
                ),
            )
        )
        cell_map[(None, season)] = heat_cells[-1]
    if years:
        rows.append(
            ft.Row(
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=summary_cells,
            )
        )

    matrix = ft.Column(
        width=matrix_width,
        spacing=4,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=rows,
    )
    matrix_row = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        scroll=ft.Scrollbar(
            orientation=ft.ScrollbarOrientation.BOTTOM,
            thumb_visibility=True,
            track_visibility=True,
        ),
        controls=[matrix],
    )

    def on_blank_tap(event: ft.ControlEvent) -> None:
        if time.monotonic() - last_show["time"] < 0.15:
            return
        clear_layers()
        reset_heat_zoom(page)

    page_col = scroll_page(
        [matrix_row],
        spacing=10,
    )
    content = ft.GestureDetector(
        expand=True,
        on_tap=on_blank_tap,
        content=page_col,
    )
    view = _back_view(
        page,
        route="/statistics/broadcast/quarter",
        title="季度",
        controls=[content],
        rebuild=lambda: quarter_view(page),
    )
    scroll_memory.remember(
        page, "/statistics/broadcast/quarter", "page", page_col
    )
    scroll_memory.remember(
        page, "/statistics/broadcast/quarter", "matrix", matrix_row
    )
    if animate:
        page.run_task(
            animate_heat_cells,
            page,
            heat_cells,
            seconds=ANIMATION_SECONDS,
        )
    return view


def _open_quarter_grid(page: ft.Page) -> None:
    route = "/statistics/broadcast/year-quarter"
    if page.views and getattr(page.views[-1], "route", "") == route:
        return
    records = load_records()
    view = build_quarter_view(
        page,
        records,
        records[0] if records else {},
        route,
    )

    def back(event: ft.ControlEvent) -> None:
        go_back(
            page,
            route,
            lambda: _hide_page_overlay(page),
        )

    if view.appbar is not None:
        view.appbar.automatically_imply_leading = False
        view.appbar.leading = back_icon(
            page,
            route,
            before=lambda: _hide_page_overlay(page),
        )
    push_view(page, view)


