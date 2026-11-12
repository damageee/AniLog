"""通用虚拟搜索页。"""

from __future__ import annotations

from typing import Callable

import flet as ft
from bangumi.ui.anim import animation

from bangumi.core.pinyin_search import (
    matches as pinyin_matches,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.constants import (
    ANIM_BASE_MS,
    HOVER_ROW_OPACITY,
)
from bangumi.ui.events import is_hover
from bangumi.ui import scroll_memory
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.views.templates.page_shell import make_view
from bangumi.views.widgets.virtual_window import (
    clamp_scroll,
    max_scroll_offset,
    window_bounds,
    window_size,
)


def _back_view(
    page: ft.Page,
    *,
    route: str,
    title: str,
    controls: list[ft.Control],
    rebuild: Callable[[], ft.View] | None = None,
) -> ft.View:
    return make_view(
        page,
        route=route,
        title=title,
        controls=controls,
        rebuild=rebuild,
        back=True,
        scroll=False,
    )


def no_result_control(page: ft.Page) -> ft.Control:
    fg = foreground_color(page)
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=20),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ui_text(
                    "无结果",
                    size=15,
                    color=ft.Colors.with_opacity(0.55, fg),
                )
            ],
        ),
    )


def wrap_search_row(
    page: ft.Page,
    row: ft.Control,
    fg: str,
) -> ft.Container:
    holder = ft.Container(
        content=row,
        animate=animation(
            ANIM_BASE_MS, ft.AnimationCurve.EASE_OUT
        ),
    )

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        holder.bgcolor = (
            ft.Colors.with_opacity(HOVER_ROW_OPACITY, fg)
            if hovered
            else None
        )
        try:
            holder.update()
        except Exception:
            pass

    holder.on_hover = on_hover
    return holder


def virtual_search_page(
    page: ft.Page,
    *,
    title: str,
    route: str,
    hint_text: str,
    all_rows: list,
    row_builder: Callable[[object, str], ft.Control],
    initial_query: str = "",
    rebuild: Callable[[str], ft.View] | None = None,
) -> ft.View:
    page_rebuild = rebuild
    ROW_HEIGHT = 40.0
    FIRST_SCREEN = 120
    fg = foreground_color(page)
    state = {
        "query": initial_query,
        "matches": [
            item
            for item in all_rows
            if not initial_query
            or pinyin_matches(item[0], initial_query)
        ],
        "start": -1,
        "first": -1,
        "end": -1,
    }

    def visible_rows() -> int:
        height = max(200.0, float(page.height or 800) - 200)
        return window_size(height, ROW_HEIGHT, extra=6)

    column = ft.Column(
        expand=True,
        spacing=0,
        scroll=ft.Scrollbar(
            orientation=ft.ScrollbarOrientation.RIGHT,
            thumb_visibility=True,
            track_visibility=True,
        ),
    )

    def rebuild(pixels: float, *, force: bool = False) -> None:
        total = len(state["matches"])
        if total == 0:
            column.controls = [
                no_result_control(page),
                ft.Container(
                    height=36,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        "共0条结果",
                        size=12,
                        color=ft.Colors.with_opacity(0.55, fg),
                    ),
                ),
            ]
            state["first"] = -1
            state["end"] = -1
            return
        window = visible_rows()
        height = max(200.0, float(page.height or 800) - 200)
        max_offset = max_scroll_offset(total, ROW_HEIGHT, height)
        clamped = clamp_scroll(float(pixels), max_offset)
        first, last_inclusive = window_bounds(
            clamped,
            total,
            window,
            ROW_HEIGHT,
            overscan=2,
        )
        last = min(total, last_inclusive + 1)
        if not force and state["first"] <= first and last <= state["end"]:
            return
        state["first"] = first
        state["end"] = last
        controls: list[ft.Control] = []
        if first > 0:
            controls.append(
                ft.Container(height=first * ROW_HEIGHT)
            )
        controls.extend(
            wrap_search_row(
                page,
                row_builder(item, state["query"]),
                fg,
            )
            for item in state["matches"][first:last]
        )
        tail = total - last
        if tail > 0:
            controls.append(
                ft.Container(height=tail * ROW_HEIGHT)
            )
        if tail <= 0:
            controls.append(
                ft.Container(
                    height=36,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        f"共{total}条结果",
                        size=12,
                        color=ft.Colors.with_opacity(0.55, fg),
                    ),
                )
            )
        column.controls = controls
        try:
            column.update()
        except Exception:
            pass

    def on_scroll(event: ft.OnScrollEvent) -> None:
        pixels = float(getattr(event, "pixels", 0) or 0)
        rebuild(pixels)

    column.on_scroll = on_scroll
    scroll_memory.remember(page, route, "list", column)

    async def _reset_scroll() -> None:
        try:
            await column.scroll_to(offset=0)
        except Exception:
            pass

    def on_search(event: ft.ControlEvent) -> None:
        needle = str(search.value or "").strip()
        state["query"] = needle
        if isinstance(view.data, dict):
            view.data["query"] = needle
        state["matches"] = [
            item
            for item in all_rows
            if not needle or pinyin_matches(item[0], needle)
        ]
        state["start"] = -1
        state["first"] = -1
        state["end"] = -1
        rebuild(0.0, force=True)
        page.run_task(_reset_scroll)

    search = ft.TextField(
        value=initial_query,
        hint_text=hint_text,
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        border_radius=8,
        on_change=on_search,
    )
    rebuild(0.0, force=True)
    view = _back_view(
        page,
        route=route,
        title=title,
        controls=[
            ft.Column(
                expand=True,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[search, column],
            )
        ],
    )
    view.data = {
        "query": state["query"],
        "rebuild": (
            (lambda: page_rebuild(state["query"]))
            if page_rebuild is not None
            else (
                lambda: virtual_search_page(
                    page,
                    title=title,
                    route=route,
                    hint_text=hint_text,
                    all_rows=all_rows,
                    row_builder=row_builder,
                    initial_query=state["query"],
                )
            )
        ),
    }
    return view
