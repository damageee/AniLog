"""按日历查看某月补完记录：上方日历，下方当日/当月列表。"""

from __future__ import annotations

import asyncio
import calendar as cal
import datetime as dt
from math import ceil

import flet as ft

from bangumi.core.cover_proc import processed_cover
from bangumi.data.dates import parse_iso_date
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.ratings import parse_rating
from bangumi.data.statistics.journey import journey_data
from bangumi.data.statistics.records import _record_item
from bangumi.data.sorting import sort_detail_items
from bangumi.data.watched_data import Record
from bangumi.ui.anim import animation
from bangumi.ui.colors import foreground_color
from bangumi.ui.events import is_hover
from bangumi.ui.layout import vertical_page
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import push_view
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.views.statistics.common.overlays import _hide_page_overlay
from bangumi.views.statistics.common.shared import _accent, _back_view
from bangumi.views.templates.list_page import open_entry_with_back

_EMPTY_MONTH_MESSAGE = "你呀，真是怠惰呢！"
_EMPTY_MONTH_COLOR = "#166534"
_EMPTY_MONTH_SIZE = 30

# 日历格尺寸与间距。
_GAP = 4.0
_COVER_RATIO = 480 / 679
_THUMB_W = 160
_HEADER_H = 14.0
_HEADER_GAP = 6.0
_ARROW_W = 34.0
_ARROW_H = 34.0
_ARROW_GAP = 6.0
_SCROLLBAR_W = 18.0
SLIDE_MS = 275
FADE_OUT_MS = 150
FADE_IN_MS = 184
EMPTY_FADE_OUT_MS = 180
EMPTY_FADE_IN_MS = 200
EMPTY_FLASH_MS = 80
EMPTY_FLASH_OPACITY = 0.5
_WEEKDAYS = ("月", "火", "水", "木", "金", "土", "日")


def _month_records(
    records: list[Record],
    year: int,
    month: int,
) -> list[Record]:
    result: list[Record] = []
    for record in records:
        date = parse_iso_date(
            str(record.get("completion") or "")
        )
        if (
            date is not None
            and date.year == year
            and date.month == month
        ):
            result.append(record)
    return result


def open_completion_month(
    page: ft.Page,
    year: int,
    month: int,
    records: list[Record] | None = None,
    *,
    push: bool = True,
    switch_handler=None,
    arrows_out: list | None = None,
    hide_arrows: bool = False,
    animated_stack: ft.Stack | None = None,
    initial_dx: float = 0.0,
    initial_visible: bool = True,
    out: dict | None = None,
) -> ft.View | None:
    """打开某个月的补完日历；没有记录时显示空状态页。"""
    route = f"/statistics/journey/month/{year}-{month:02d}"

    def load_source() -> list[Record]:
        if records is None:
            return journey_data().records
        return records

    source = load_source()
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    month_records = _month_records(source, year, month)
    title = f"{year}.{month:02d} 补完 ({len(month_records)})"
    state = {
        "year": year,
        "month": month,
        "records": source,
        "empty": not month_records,
        "animating": False,
        "arrows": [],
        "calendar_width": 0.0,
        "build": out if out is not None else {},
    }
    arrow_sink = arrows_out if arrows_out is not None else []
    state["arrows"] = arrow_sink

    def stage_width() -> float:
        return max(
            280.0,
            float(page.width or 1000) - 48.0 - _SCROLLBAR_W,
        )

    def content_width() -> float:
        return max(
            280.0,
            stage_width() - 2.0 * (_ARROW_W + _ARROW_GAP),
        )

    view_ref: dict[str, ft.View] = {}

    def switch_month(delta: int) -> None:
        """原地切换到相邻月份，并用滑动/淡入淡出过渡。"""
        if state["animating"]:
            return
        state["animating"] = True
        total = state["year"] * 12 + (state["month"] - 1) + delta
        ny, nm = total // 12, total % 12 + 1
        page.run_task(_animate_switch, ny, nm, delta)

    async def _animate_switch(
        ny: int,
        nm: int,
        delta: int,
    ) -> None:
        view = view_ref.get("view")
        if view is None:
            state["animating"] = False
            return
        old = state.get("build") or {}
        old_stack = old.get("stack")
        old_layer = old.get("layer")
        new_arrows: list = []
        new_out: dict = {}
        body_width = stage_width()
        calendar_w = float(
            state.get("calendar_width") or body_width
        )
        slide = min(
            0.4,
            max(0.06, calendar_w * 0.5 / body_width),
        )
        sign = 1 if delta > 0 else -1
        new_records = _month_records(state["records"], ny, nm)
        fade_only = bool(state["empty"] or not new_records)
        new_view = open_completion_month(
            page,
            ny,
            nm,
            records=state["records"],
            push=False,
            switch_handler=switch_month,
            arrows_out=new_arrows,
            hide_arrows=True,
            animated_stack=(None if fade_only else old_stack),
            initial_dx=(
                0.0 if fade_only else float(sign) * slide
            ),
            initial_visible=bool(fade_only),
            out=new_out,
        )
        if new_view is None:
            state["animating"] = False
            return

        # 两页都为空：中间文字快速闪烁，不做页面切换动画。
        if state["empty"] and not new_records:
            holder = state.get("content_holder")
            new_content = new_out.get("content")
            if holder is not None:
                # 先建立透明度动画规格（Flet 隐式动画要求）。
                holder.animate_opacity = animation(
                    EMPTY_FLASH_MS, ft.AnimationCurve.EASE_OUT
                )
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(0.02)
                holder.opacity = EMPTY_FLASH_OPACITY
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(
                    EMPTY_FLASH_MS / 1000 + 0.01
                )
                # 两页文字相同，换内容后淡回。
                if new_content is not None:
                    holder.content = new_content
                holder.opacity = 1
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(
                    EMPTY_FLASH_MS / 1000 + 0.01
                )
                holder.animate_opacity = None
            else:
                body = (
                    new_view.controls[0]
                    if new_view.controls
                    else None
                )
                if body is not None:
                    view.controls = [body]

            state["build"] = new_out
            state["calendar_width"] = float(
                new_out.get("calendar_width") or calendar_w
            )
            view.route = new_view.route
            view.appbar = new_view.appbar
            view.data = new_view.data
            state["year"] = ny
            state["month"] = nm
            state["empty"] = True
            state["animating"] = False
            try:
                view.update()
            except Exception:
                pass
            return

        # 滑动前先隐藏旧箭头。
        for arrow in state.get("arrows", []):
            arrow.visible = False
            try:
                arrow.update()
            except Exception:
                pass

        new_layer = new_out.get("layer")
        if (
            not fade_only
            and old_stack is not None
            and old_layer is not None
            and new_layer is not None
        ):
            # 新旧日历同时滑动/淡入淡出。
            old_h = float(old.get("height") or 0.0)
            new_h = float(new_out.get("height") or 0.0)
            old_stack.height = max(old_h, new_h)
            # 新 layer 首帧直接位于起点并隐藏，避免先闪到 offset=0。
            new_layer.visible = True
            new_layer.offset = (float(sign) * slide, 0.0)
            new_layer.opacity = 0
            try:
                old_stack.update()
            except Exception:
                pass
            await asyncio.sleep(0.03)
            # 阶段 1：只建立动画规格，不改数值。
            old_layer.animate_offset = animation(
                SLIDE_MS, ft.AnimationCurve.EASE_IN_OUT
            )
            old_layer.animate_opacity = animation(
                FADE_OUT_MS, ft.AnimationCurve.EASE_IN_OUT
            )
            new_layer.animate_offset = animation(
                SLIDE_MS, ft.AnimationCurve.EASE_IN_OUT
            )
            new_layer.animate_opacity = animation(
                FADE_IN_MS, ft.AnimationCurve.EASE_IN_OUT
            )
            try:
                old_stack.update()
            except Exception:
                pass
            await asyncio.sleep(0.03)
            # 阶段 2：再改变数值，触发动画。
            old_layer.offset = (
                float(-sign) * slide,
                0.0,
            )
            old_layer.opacity = 0
            new_layer.offset = (0.0, 0.0)
            new_layer.opacity = 1
            try:
                old_stack.update()
            except Exception:
                pass
            await asyncio.sleep(SLIDE_MS / 1000 + 0.03)
            old_stack.controls = [new_layer]
            new_layer.animate_offset = None
            new_layer.animate_opacity = None
            new_layer.offset = (0.0, 0.0)
            new_layer.opacity = 1
            old_stack.height = float(
                new_out.get("height") or old_stack.height or 0.0
            )
            # 列表在动画结束后再刷新，避免影响滚动条/宽度。
            if callable(old.get("refresh_list")):
                old["refresh_list"](new_records)
                new_out["refresh_list"] = old["refresh_list"]
        else:
            # 任一月份为空：只对内容容器做透明度切换。
            holder = state.get("content_holder")
            new_content = new_out.get("content")
            if holder is not None and new_content is not None:
                # 阶段 1：建立淡出动画规格。
                holder.animate_opacity = animation(
                    EMPTY_FADE_OUT_MS, ft.AnimationCurve.EASE_IN_OUT
                )
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(0.02)
                # 阶段 2：触发淡出。
                holder.opacity = 0
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(
                    EMPTY_FADE_OUT_MS / 1000 + 0.03
                )
                holder.animate_opacity = None
                holder.content = new_content
                # 阶段 1：建立淡入动画规格。
                holder.animate_opacity = animation(
                    EMPTY_FADE_IN_MS, ft.AnimationCurve.EASE_IN_OUT
                )
                holder.opacity = 0
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(0.02)
                # 阶段 2：触发淡入。
                holder.opacity = 1
                try:
                    holder.update()
                except Exception:
                    pass
                await asyncio.sleep(
                    EMPTY_FADE_IN_MS / 1000 + 0.03
                )
                holder.animate_opacity = None
                # 淡入完成后再刷新新列表（若有）。
                refresh = new_out.get("refresh_list")
                if callable(refresh):
                    refresh(new_records)

        # 恢复固定箭头显示（箭头不参与内容动画）。
        for arrow in state.get("arrows", []):
            arrow.visible = True
            try:
                arrow.update()
            except Exception:
                pass
        state["build"] = new_out
        state["calendar_width"] = float(
            new_out.get("calendar_width") or calendar_w
        )
        # 原地改路由/标题/刷新回调。
        view.route = new_view.route
        view.appbar = new_view.appbar
        view.data = new_view.data
        state["year"] = ny
        state["month"] = nm
        state["empty"] = not new_records
        state["animating"] = False
        try:
            view.update()
        except Exception:
            pass

    arrow_callback = switch_handler or switch_month

    def arrow_hover(
        event: ft.ControlEvent,
        button: ft.IconButton,
    ) -> None:
        button.icon_color = fg if is_hover(event) else secondary
        try:
            button.update()
        except Exception:
            pass

    def month_arrow(
        icon,
        tooltip: str,
        delta: int,
    ) -> ft.IconButton:
        button = ft.IconButton(
            icon=icon,
            icon_size=30,
            icon_color=secondary,
            width=_ARROW_W,
            height=_ARROW_H,
            padding=ft.Padding.all(0),
            tooltip=tooltip,
            visible=not hide_arrows,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                overlay_color=ft.Colors.with_opacity(0.08, fg),
            ),
        )
        arrow_sink.append(button)
        button.on_hover = lambda event, b=button: arrow_hover(
            event, b
        )
        button.on_click = lambda event, d=delta: arrow_callback(d)
        return button

    left_arrow: ft.IconButton | None = None
    right_arrow: ft.IconButton | None = None
    if not hide_arrows:
        left_arrow = month_arrow(
            ft.Icons.ARROW_BACK_OUTLINED,
            "上一个月",
            -1,
        )
        right_arrow = month_arrow(
            ft.Icons.ARROW_FORWARD_OUTLINED,
            "下一个月",
            1,
        )
        state["arrows"] = [left_arrow, right_arrow]

    def wrap_page(view: ft.View) -> ft.View:
        """把内容放进固定左右箭头的页面主体布局。"""
        initial_content = (
            view.controls[0] if view.controls else None
        )
        holder = ft.Container(
            expand=True,
            content=initial_content,
        )
        page_body = ft.Stack(
            expand=True,
            controls=[
                ft.Container(
                    left=0,
                    top=0,
                    right=0,
                    bottom=0,
                    content=holder,
                ),
                ft.Container(
                    left=0,
                    top=0,
                    bottom=0,
                    width=_ARROW_W,
                    alignment=ft.Alignment.CENTER,
                    content=left_arrow,
                ),
                ft.Container(
                    right=_SCROLLBAR_W,
                    top=0,
                    bottom=0,
                    width=_ARROW_W,
                    alignment=ft.Alignment.CENTER,
                    content=right_arrow,
                ),
            ],
        )
        view.controls = [page_body]
        state["content_holder"] = holder
        build = state.get("build")
        if isinstance(build, dict):
            build["content"] = initial_content
        return view

    if not month_records:
        _hide_page_overlay(page)
        if (
            page.views
            and getattr(page.views[-1], "route", "") == route
        ):
            return

        def build_empty() -> ft.View:
            empty_text = ui_text(
                _EMPTY_MONTH_MESSAGE,
                size=_EMPTY_MONTH_SIZE,
                color=_EMPTY_MONTH_COLOR,
                weight=ft.FontWeight.BOLD,
            )
            empty_body = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=(
                    ft.CrossAxisAlignment.CENTER
                ),
                controls=[empty_text],
            )
            build_out = state.get("build")
            if isinstance(build_out, dict):
                build_out["stack"] = None
                build_out["layer"] = empty_body
                build_out["content"] = empty_body
                build_out["arrows"] = arrow_sink
                build_out["empty"] = True
                build_out["calendar_width"] = 0.0
            return _back_view(
                page,
                route=route,
                title=title,
                rebuild=build_empty,
                controls=[empty_body],
            )

        view = build_empty()
        if not hide_arrows:
            view = wrap_page(view)
        view_ref["view"] = view
        if not push:
            return view
        push_view(page, view)
        return

    _hide_page_overlay(page)
    if page.views and getattr(page.views[-1], "route", "") == route:
        return

    green = _accent(page, "#16A34A", "#4ADE80")

    def build_month_view(fresh: list[Record]) -> ft.View:
        fresh_month = _month_records(fresh, year, month)
        fresh_title = f"{year}.{month:02d} 补完 ({len(fresh_month)})"
        by_day: dict[int, list[Record]] = {}
        for record in fresh_month:
            date = parse_iso_date(
                str(record.get("completion") or "")
            )
            if date is None:
                continue
            by_day.setdefault(date.day, []).append(record)

        def day_cover(
            day_records: list[Record],
        ) -> bytes | None:
            """挑选当天的代表封面（评分高、放送早优先）。"""
            candidates: list[
                tuple[tuple[int, tuple[int, int, int, int]], bytes]
            ] = []
            for record in day_records:
                bgm_id = record.get("bgm_id")
                if not isinstance(bgm_id, int) or bgm_id == -1:
                    continue
                data = processed_cover(bgm_id, _THUMB_W)
                if data is None:
                    continue
                rating = parse_rating(record.get("rating")) or 0
                start = earliest_broadcast_date(
                    str(record.get("broadcast") or "")
                )
                date_key = (
                    (1, 0, 0, 0)
                    if start is None
                    else (0, *start)
                )
                candidates.append(
                    ((-rating, date_key), data)
                )
            if not candidates:
                return None
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]

        def hover_cell(
            event: ft.ControlEvent,
            cell: ft.Container,
        ) -> None:
            cell.scale = 1.08 if is_hover(event) else 1.0
            try:
                cell.update()
            except Exception:
                pass

        list_title_text = ui_text(
            "本月补完的动画",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=fg,
        )
        list_holder = ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        hover_row = ft.Colors.with_opacity(0.06, fg)

        def row_hover(
            event: ft.ControlEvent,
            row: ft.Container,
        ) -> None:
            row.bgcolor = hover_row if is_hover(event) else None
            try:
                row.update()
            except Exception:
                pass

        def make_row(
            text: str,
            record: Record,
        ) -> ft.Container:
            row = ft.Container(
                padding=ft.Padding.symmetric(
                    horizontal=6,
                    vertical=9,
                ),
                border_radius=6,
                border=ft.Border(
                    bottom=ft.BorderSide(
                        1,
                        ft.Colors.with_opacity(0.2, fg),
                    )
                ),
                tooltip="打开条目页",
                content=ui_text(text, size=15),
            )
            row.on_click = (
                lambda event, r=record: open_entry_with_back(
                    page,
                    fresh,
                    r,
                    before=lambda: _hide_page_overlay(page),
                )
            )
            row.on_hover = (
                lambda event, c=row: row_hover(event, c)
            )
            return row

        def fill_list(items: list[Record]) -> None:
            # _record_item 已返回 (text, record)，不要再包一层。
            ordered = sort_detail_items(
                [_record_item(record) for record in items]
            )
            controls: list[ft.Control] = [
                make_row(text, record)
                for text, record in ordered
            ]
            if not controls:
                controls = [ui_text("暂无数据", size=15)]
            list_holder.controls = controls

        def select_day(day: int) -> None:
            list_title_text.value = "该日补完的动画"
            fill_list(by_day.get(day, []))
            for control in (list_title_text, list_holder):
                try:
                    control.update()
                except Exception:
                    pass

        def calendar_metrics(rows_count: int) -> tuple[float, float]:
            """按窗口尺寸计算日历格宽高，优先占满高度。"""
            appbar_h = 56.0
            margin = 16.0
            avail_w = max(280.0, content_width())
            avail_h = max(
                220.0,
                float(page.height or 800) - appbar_h - margin,
            )
            w_by_width = avail_w / 7
            h_by_height = (
                avail_h
                - _HEADER_H
                - _HEADER_GAP
            ) / max(1, rows_count)
            w_by_height = h_by_height * _COVER_RATIO
            cell_w = max(20.0, min(w_by_width, w_by_height))
            cell_h = cell_w / _COVER_RATIO
            return cell_w, cell_h

        # 日历：周一起始。
        first = dt.date(year, month, 1)
        leading = first.weekday()
        days = cal.monthrange(year, month)[1]
        rows = ceil((leading + days) / 7)
        cell_w, cell_h = calendar_metrics(rows)
        state["calendar_width"] = (
            cell_w * 7 + 2 * (_ARROW_W + _ARROW_GAP)
        )

        weekday_boxes: list[ft.Container] = [
            ft.Container(
                width=cell_w,
                height=_HEADER_H,
                alignment=ft.Alignment.CENTER,
                content=ui_text(
                    name,
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=secondary,
                ),
            )
            for name in _WEEKDAYS
        ]
        weekday_row = ft.Row(
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=weekday_boxes,
        )

        # 网格使用无缝单元格：列间/行间由边框画出分隔线。
        thin = ft.Colors.with_opacity(0.12, fg)
        thick = ft.Colors.with_opacity(0.65, ft.Colors.BLACK)
        resize_cells: list[
            tuple[ft.Container, ft.Control | None]
        ] = []
        grid_rows: list[ft.Control] = []
        for row_index in range(rows):
            cells: list[ft.Control] = []
            for column_index in range(7):
                day = (
                    row_index * 7 + column_index - leading + 1
                )
                edges: dict[
                    str, ft.BorderSide | None
                ] = {
                    "top": (
                        ft.BorderSide(2, thick)
                        if row_index == 0
                        else None
                    ),
                    "right": (
                        ft.BorderSide(1, thin)
                        if column_index < 6
                        else None
                    ),
                    "bottom": (
                        ft.BorderSide(1, thin)
                        if row_index < rows - 1
                        else None
                    ),
                    "left": None,
                }
                if day < 1 or day > days:
                    blank = ft.Container(
                        width=cell_w,
                        height=cell_h,
                        border_radius=0,
                        border=ft.Border(**edges),
                    )
                    resize_cells.append((blank, None))
                    cells.append(blank)
                    continue
                day_records = by_day.get(day, [])
                image: ft.Control | None = None
                if not day_records:
                    content: ft.Control = ui_text(
                        str(day),
                        size=12,
                        color=secondary,
                    )
                else:
                    thumb = day_cover(day_records)
                    if thumb is not None:
                        content = ft.Image(
                            src=thumb,
                            width=cell_w,
                            height=cell_h,
                            fit=ft.BoxFit.COVER,
                        )
                        image = content
                    else:
                        content = ui_text(
                            str(day),
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=green,
                        )
                cell_box = ft.Container(
                    width=cell_w,
                    height=cell_h,
                    border_radius=0,
                    border=ft.Border(**edges),
                    alignment=ft.Alignment.CENTER,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    scale=1.0,
                    animate_scale=animation(
                        140,
                        ft.AnimationCurve.EASE_OUT,
                    ),
                    content=content,
                )
                if day_records:
                    cell_box.on_hover = (
                        lambda event, c=cell_box: hover_cell(
                            event,
                            c,
                        )
                    )
                    cell_box.on_click = (
                        lambda event, d=day: select_day(d)
                    )
                resize_cells.append((cell_box, image))
                cells.append(cell_box)
            grid_rows.append(
                ft.Row(
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=cells,
                )
            )
        calendar_column = ft.Column(
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                weekday_row,
                ft.Container(height=_HEADER_GAP),
                *grid_rows,
            ],
        )
        # 窗口尺寸变化时只更新日历格子，不重建列表。
        resize_token = {"value": 0}

        def on_page_resize(event=None) -> None:
            if not (
                page.views
                and str(getattr(page.views[-1], "route", "")) == route
            ):
                return
            resize_token["value"] += 1
            token = resize_token["value"]

            async def apply() -> None:
                await asyncio.sleep(0.15)
                if resize_token["value"] != token:
                    return
                new_w, new_h = calendar_metrics(rows)
                for box, image in resize_cells:
                    box.width = new_w
                    box.height = new_h
                    if isinstance(image, ft.Image):
                        image.width = new_w
                        image.height = new_h
                    try:
                        box.update()
                    except Exception:
                        pass
                for box in weekday_boxes:
                    box.width = new_w
                    try:
                        box.update()
                    except Exception:
                        pass
                grid_w = new_w * 7
                weekday_row.width = grid_w
                calendar_column.width = grid_w
                for control in (
                    weekday_row,
                    calendar_column,
                ):
                    try:
                        control.update()
                    except Exception:
                        pass
                body_w = stage_width()
                new_cal_h = (
                    _HEADER_H + _HEADER_GAP + rows * new_h
                )
                target_stack.width = body_w
                target_stack.height = new_cal_h
                try:
                    target_stack.update()
                except Exception:
                    pass
                for child in target_stack.controls:
                    child.width = body_w
                    try:
                        child.update()
                    except Exception:
                        pass

            page.run_task(apply)

        def on_resize_event(event=None) -> None:
            # 仅栈顶响应
            if not (
                page.views
                and str(getattr(page.views[-1], "route", "")) == route
            ):
                return
            on_page_resize(event)

        register_resize_handler(page, route, on_resize_event)

        fill_list(fresh_month)
        body_width = stage_width()
        cal_h = _HEADER_H + _HEADER_GAP + rows * cell_h
        target_stack = (
            animated_stack
            if animated_stack is not None
            else ft.Stack(
                width=body_width,
                height=cal_h,
                controls=[],
            )
        )
        layer = ft.Container(
            width=body_width,
            alignment=ft.Alignment.TOP_CENTER,
            content=calendar_column,
        )
        layer.offset = (
            initial_dx if not initial_visible else 0.0,
            0.0,
        )
        layer.opacity = 1 if initial_visible else 0
        if not initial_visible:
            layer.visible = False
        target_stack.width = body_width
        target_stack.height = cal_h
        target_stack.controls = [*target_stack.controls, layer]
        inner = ft.Column(
            spacing=10,
            controls=[
                target_stack,
                list_title_text,
                list_holder,
            ],
        )
        body = vertical_page([inner], stretch=True)
        build_out = out if out is not None else state.get("build")
        if isinstance(build_out, dict):
            build_out["stack"] = target_stack
            build_out["layer"] = layer
            build_out["height"] = cal_h
            build_out["content"] = body
            build_out["arrows"] = arrow_sink
            build_out["empty"] = False
            build_out["calendar_width"] = cell_w * 7
            build_out["refresh_list"] = fill_list
        return _back_view(
            page,
            route=route,
            title=fresh_title,
            controls=[body],
            rebuild=lambda: build_month_view(load_source()),
        )

    view = build_month_view(source)
    if not hide_arrows:
        view = wrap_page(view)
    view_ref["view"] = view
    if not push:
        return view
    push_view(page, view)
    return
