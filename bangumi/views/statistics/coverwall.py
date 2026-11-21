"""照片墙页面：随机展示有缓存封面的已阅作品。"""

from __future__ import annotations

import asyncio
import os
import random
from concurrent.futures import ThreadPoolExecutor

import flet as ft

from bangumi.core.cover_proc import processed_cover
from bangumi.data.favorites import (
    LIKES_ID,
    LIKES_NAME,
    load_favorites,
)
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import Record, load_records
from bangumi.services.bgm_pic import record_has_cover
from bangumi.ui.anim import animation, entry_animations_enabled
from bangumi.ui.colors import foreground_color
from bangumi.ui.events import is_hover
from bangumi.ui.interaction import hover_icon
from bangumi.ui.platform import is_mobile
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.navigation import ENTRY, open_detail
from bangumi.views.statistics.common.shared import _back_view

# 尺寸文案与每行数量（桌面 / 移动端）。
_SIZE_ORDER = ("中", "小", "大")
_PER_ROW = {"小": 20, "中": 12, "大": 6}
_PER_ROW_MOBILE = {"小": 10, "中": 6, "大": 3}


def per_row_for(page: ft.Page, size: str) -> int:
    """按平台返回当前尺寸的每行数量。"""
    table = _PER_ROW_MOBILE if is_mobile(page) else _PER_ROW
    return int(table.get(size, table["中"]))


def coverwall_view(page: ft.Page) -> ft.View:
    """照片墙页面。"""
    route = "/statistics/coverwall"
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    records = load_records()
    favorite_data = load_favorites()
    eligible = [
        record for record in records if record_has_cover(record)
    ]
    animate = entry_animations_enabled()

    years: set[int] = set()
    for record in eligible:
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        if date is not None:
            years.add(date[0])

    # 读取上一次的筛选状态，窗口重建后保持选择。
    prev: dict = {}
    if page.views:
        top = page.views[-1]
        if (
            str(getattr(top, "route", "")) == "/statistics/coverwall"
            and isinstance(getattr(top, "data", None), dict)
        ):
            prev = dict(top.data)
    prev_size = prev.get("cover_size")
    if prev_size not in _SIZE_ORDER:
        prev_size = "中"

    state: dict[str, object] = {
        "year": prev.get("cover_year"),
        "folder": prev.get("cover_folder"),
        "size": prev_size,
        "ids": [],
        "grid_w": 0.0,
        "grid_h": 0.0,
        "per_row": per_row_for(page, str(prev_size)),
        "cell_w": 0.0,
        "cell_h": 0.0,
        "spacing": 8.0,
        "rows": 0,
        "initialized": False,
    }

    def current_year() -> int | None:
        value = state["year"]
        return value if isinstance(value, int) else None

    def folder_uids() -> set[str] | None:
        """返回当前收藏夹的 uid 集合；未选择收藏夹返回 None。"""
        folder_id = state["folder"]
        if not isinstance(folder_id, str):
            return None
        items: object = None
        if folder_id == LIKES_ID:
            items = favorite_data.get("likes")
        else:
            folders = favorite_data.get("folders")
            if isinstance(folders, list):
                for folder in folders:
                    if (
                        isinstance(folder, dict)
                        and str(folder.get("id") or "")
                        == folder_id
                    ):
                        items = folder.get("items")
                        break
        if not isinstance(items, list):
            return set()
        return {
            str(item.get("uid") or "")
            for item in items
            if isinstance(item, dict)
        }

    def pool_for(year: int | None) -> list[Record]:
        if year is None:
            pool = list(eligible)
        else:
            pool = []
            for record in eligible:
                date = earliest_broadcast_date(
                    str(record.get("broadcast") or "")
                )
                if date is not None and date[0] == year:
                    pool.append(record)
        uids = folder_uids()
        if uids is not None:
            pool = [
                record
                for record in pool
                if str(record.get("uid") or "") in uids
            ]
        return pool

    def grid_metrics(
        per_row: int,
        width: float,
        height: float,
    ) -> tuple[float, float, int, float]:
        # 直接用 GridView 实测宽高计算，列数即 per_row。
        spacing = max(2.0, min(8.0, width / (per_row * 16.0)))
        cell_w = max(
            16,
            int(
                (width - spacing * (per_row - 1))
                / per_row
            ),
        )
        cell_h = int(cell_w / 0.707)
        rows = max(
            1,
            int((height + spacing) // (cell_h + spacing)),
        )
        return float(cell_w), float(cell_h), rows, spacing

    def page_alive() -> bool:
        return any(
            str(getattr(view, "route", "")) == route
            for view in page.views
        )

    grid = ft.GridView(
        expand=True,
        runs_count=per_row_for(page, str(prev_size)),
        child_aspect_ratio=0.707,
        spacing=float(state["spacing"]),
        run_spacing=float(state["spacing"]),
        padding=0,
        controls=[],
    )

    def hover_item(
        event: ft.ControlEvent,
        item: ft.Container,
    ) -> None:
        hovered = is_hover(event)
        item.scale = 1.03 if hovered else 1.0
        try:
            item.update()
        except Exception:
            pass

    def make_item(
        record: Record,
        data: bytes,
        cell_w: float,
        cell_h: float,
        target_w: int,
    ) -> ft.Container:
        image = ft.Image(
            src=data,
            width=cell_w,
            height=cell_h,
            fit=ft.BoxFit.COVER,
        )
        item = ft.Container(
            width=cell_w,
            height=cell_h,
            border_radius=4,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            scale=ft.Scale(0.0) if animate else ft.Scale(1.0),
            animate_scale=animation(
                200,
                ft.AnimationCurve.EASE_OUT,
            ),
            content=image,
        )
        item.on_hover = (
            lambda event, c=item: hover_item(event, c)
        )
        item.on_click = (
            lambda event, r=record: open_detail(
                page,
                records,
                r,
                ENTRY,
            )
        )
        return item

    def build_items(
        picked: list[Record],
        cell_w: float,
        cell_h: float,
        target_w: int,
    ) -> list[ft.Container]:
        if not picked:
            return []

        def work(record: Record) -> ft.Container | None:
            bgm_id = record.get("bgm_id")
            if not isinstance(bgm_id, int) or bgm_id == -1:
                return None
            data = processed_cover(bgm_id, target_w)
            if data is None:
                return None
            return make_item(
                record,
                data,
                cell_w,
                cell_h,
                target_w,
            )

        workers = min(8, os.cpu_count() or 4)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(work, picked))
        return [
            item for item in results if item is not None
        ]

    async def run_row(
        row_index: int,
        items: list[ft.Container],
    ) -> None:
        cols = int(state["per_row"]) or 1
        half = max(1, cols // 2)
        delay = 0.025
        await asyncio.sleep(row_index * half * delay)
        for item in items:
            if not page_alive():
                return
            item.scale = ft.Scale(1.0)
            try:
                item.update()
            except Exception:
                pass
            await asyncio.sleep(delay)

    def play_animation(items: list[ft.Container]) -> None:
        if not animate or not items:
            return
        cols = int(state["per_row"]) or 1
        for start in range(0, len(items), cols):
            page.run_task(
                run_row,
                start // cols,
                items[start : start + cols],
            )

    def render(items: list[ft.Container]) -> None:
        spacing = float(state["spacing"])
        # 固定列数，避免 max_extent 再分配导致少一张。
        grid.runs_count = int(state["per_row"])
        grid.spacing = spacing
        grid.run_spacing = spacing
        if items:
            grid.controls = items
        else:
            grid.controls = [
                ui_text("暂无数据", size=12, color=secondary)
            ]
        try:
            grid.update()
        except Exception:
            pass
        play_animation(items)

    def reshuffle(force: bool = False) -> None:
        if not state["initialized"]:
            return
        per_row = per_row_for(page, str(state["size"]))
        width = float(state["grid_w"])
        height = float(state["grid_h"])
        cell_w, cell_h, rows, spacing = grid_metrics(
            per_row,
            width,
            height,
        )
        state["per_row"] = per_row
        state["cell_w"] = cell_w
        state["cell_h"] = cell_h
        state["spacing"] = spacing
        state["rows"] = rows
        sample_count = rows * per_row
        pool = pool_for(current_year())
        count = min(sample_count, len(pool))
        picked = (
            random.sample(pool, count) if count > 0 else []
        )
        ids = [record.get("bgm_id") for record in picked]
        if not force and ids == state["ids"]:
            return
        state["ids"] = ids
        items = build_items(
            picked,
            cell_w,
            cell_h,
            target_w=int(round(cell_w)),
        )
        render(items)

    def relayout(width: float, height: float) -> None:
        """窗口变化时只重排现有图片，不重新随机抽样。"""
        per_row = per_row_for(page, str(state["size"]))
        cell_w, cell_h, rows, spacing = grid_metrics(
            per_row,
            width,
            height,
        )
        state["grid_w"] = width
        state["grid_h"] = height
        state["per_row"] = per_row
        state["cell_w"] = cell_w
        state["cell_h"] = cell_h
        state["spacing"] = spacing
        state["rows"] = rows
        sample_count = rows * per_row
        by_id = {
            record.get("bgm_id"): record
            for record in eligible
            if isinstance(record.get("bgm_id"), int)
        }
        ids = [
            value
            for value in state["ids"]
            if isinstance(value, int)
        ]
        if len(ids) > sample_count:
            ids = ids[:sample_count]
        elif len(ids) < sample_count:
            used = set(ids)
            candidates = [
                record
                for record in pool_for(current_year())
                if record.get("bgm_id") not in used
            ]
            extra = min(
                sample_count - len(ids),
                len(candidates),
            )
            if extra > 0:
                ids.extend(
                    record.get("bgm_id")
                    for record in random.sample(
                        candidates,
                        extra,
                    )
                )
        state["ids"] = ids
        picked = [
            by_id[value] for value in ids if value in by_id
        ]
        items = build_items(
            picked,
            cell_w,
            cell_h,
            target_w=int(round(cell_w)),
        )
        render(items)

    year_text = ui_text(
        "全部"
        if state["year"] is None
        else str(state["year"]),
        size=12,
        color=fg,
    )
    # 两个下拉统一宽度：文字 + 内边距 + 箭头 + 间距。
    dropdown_w = max(
        60.0,
        text_width("全部", size=12) + 16 + 14 + 8,
    )

    def select_year(value: int | None) -> None:
        state["year"] = value
        year_text.value = "全部" if value is None else str(value)
        try:
            year_text.update()
        except Exception:
            pass
        sync_state()
        reshuffle(force=True)

    year_button = ft.PopupMenuButton(
        content=ft.Container(
            width=dropdown_w,
            height=32,
            padding=ft.Padding.symmetric(horizontal=8),
            border=ft.Border.all(
                1,
                ft.Colors.with_opacity(0.35, fg),
            ),
            border_radius=4,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                spacing=4,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    year_text,
                    ft.Icon(
                        ft.Icons.ARROW_DROP_DOWN,
                        size=14,
                        color=fg,
                    ),
                ],
            ),
        ),
        items=[
            ft.PopupMenuItem(
                content=ui_text("全部", size=12),
                on_click=lambda event: select_year(None),
            ),
            *[
                ft.PopupMenuItem(
                    content=ui_text(str(year), size=12),
                    on_click=(
                        lambda event, y=year: select_year(y)
                    ),
                )
                for year in sorted(years, reverse=True)
            ],
        ],
    )

    folder_options: list[tuple[str | None, str]] = [
        (None, "全部"),
        (LIKES_ID, LIKES_NAME),
    ]
    folders_raw = favorite_data.get("folders")
    if isinstance(folders_raw, list):
        for folder in folders_raw:
            if isinstance(folder, dict):
                folder_options.append(
                    (
                        str(folder.get("id") or ""),
                        str(folder.get("name") or "未命名"),
                    )
                )
    folder_label = "全部"
    for option_value, option_label in folder_options:
        if option_value == state["folder"]:
            folder_label = option_label
            break
    folder_text = ui_text(
        folder_label,
        size=12,
        color=fg,
        no_wrap=True,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    def select_folder(value: str | None) -> None:
        state["folder"] = value
        label = "全部"
        for option_value, option_label in folder_options:
            if option_value == value:
                label = option_label
                break
        folder_text.value = label
        try:
            folder_text.update()
        except Exception:
            pass
        sync_state()
        reshuffle(force=True)

    folder_button = ft.PopupMenuButton(
        content=ft.Container(
            width=dropdown_w,
            height=32,
            padding=ft.Padding.symmetric(horizontal=8),
            border=ft.Border.all(
                1,
                ft.Colors.with_opacity(0.35, fg),
            ),
            border_radius=4,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                spacing=4,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    folder_text,
                    ft.Icon(
                        ft.Icons.ARROW_DROP_DOWN,
                        size=14,
                        color=fg,
                    ),
                ],
            ),
        ),
        items=[
            ft.PopupMenuItem(
                content=ui_text(label, size=12),
                on_click=(
                    lambda event, v=value: select_folder(v)
                ),
            )
            for value, label in folder_options
        ],
    )

    size_text = ui_text(
        str(state["size"]),
        size=12,
        color=fg,
        no_wrap=True,
        max_lines=1,
    )
    size_w = max(28.0, text_width("中", size=12) + 16)

    def cycle_size(event: ft.ControlEvent) -> None:
        current = str(state["size"])
        index = (
            _SIZE_ORDER.index(current)
            if current in _SIZE_ORDER
            else 0
        )
        new_size = _SIZE_ORDER[
            (index + 1) % len(_SIZE_ORDER)
        ]
        state["size"] = new_size
        size_text.value = new_size
        try:
            size_text.update()
        except Exception:
            pass
        sync_state()
        reshuffle(force=True)

    size_button = ft.Button(
        content=size_text,
        width=size_w,
        height=32,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(
                horizontal=6,
                vertical=0,
            ),
            text_style=ui_text_style(size=12),
        ),
        on_click=cycle_size,
    )

    dice = hover_icon(
        page,
        ft.Icons.CASINO,
        tooltip="随机刷新",
        on_click=lambda event: reshuffle(),
        size=20,
        padding=6,
    )

    controls_row = ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            year_button,
            folder_button,
            size_button,
            dice,
        ],
    )

    # 简单防抖即可，GridView 自行处理排版。
    resize_token = {"value": 0}

    # 主体：控件行 + 自动铺满的 GridView。
    page_col = ft.Column(
        expand=True,
        spacing=8,
        controls=[controls_row, grid],
    )

    view = _back_view(
        page,
        route=route,
        title="照片墙",
        controls=[page_col],
        rebuild=lambda: coverwall_view(page),
    )
    if view.appbar is not None:
        view.appbar.title = ui_text("照片墙")

    def sync_state() -> None:
        """把当前选择写回 view.data，重建时恢复。"""
        data = view.data if isinstance(view.data, dict) else {}
        data["cover_year"] = state["year"]
        data["cover_folder"] = state["folder"]
        data["cover_size"] = state["size"]
        view.data = data

    # GridView 自身的实测宽高才是真正的排版依据。
    resize_token = {"value": 0}

    def on_grid_resize(event) -> None:
        width = float(getattr(event, "width", 0) or 0)
        height = float(getattr(event, "height", 0) or 0)
        if width < 200 or height < 120:
            return
        per_row = per_row_for(page, str(state["size"]))
        cell_w, cell_h, rows, spacing = grid_metrics(
            per_row,
            width,
            height,
        )
        if not state["initialized"]:
            # 首屏等 GridView 测量完成后再抽样。
            state["initialized"] = True
            state["grid_w"] = width
            state["grid_h"] = height
            state["per_row"] = per_row
            state["cell_w"] = cell_w
            state["cell_h"] = cell_h
            state["spacing"] = spacing
            state["rows"] = rows
            reshuffle(force=True)
            return
        if (
            abs(cell_w - float(state["cell_w"])) < 1
            and rows == int(state["rows"])
        ):
            return
        resize_token["value"] += 1
        token = resize_token["value"]

        async def apply() -> None:
            await asyncio.sleep(0.2)
            if resize_token["value"] != token:
                return
            relayout(width, height)

        page.run_task(apply)

    grid.on_size_change = on_grid_resize

    async def fallback_initial() -> None:
        # 某些平台不触发尺寸事件，0.6 秒后用页面尺寸估算一次。
        await asyncio.sleep(0.6)
        if state["initialized"]:
            return
        width = max(
            200.0,
            float(page.width or 1000) - 48.0 - 16.0,
        )
        height = max(
            120.0,
            float(page.height or 800) - 56.0 - 32.0,
        )
        per_row = per_row_for(page, str(state["size"]))
        cell_w, cell_h, rows, spacing = grid_metrics(
            per_row,
            width,
            height,
        )
        state["initialized"] = True
        state["grid_w"] = width
        state["grid_h"] = height
        state["per_row"] = per_row
        state["cell_w"] = cell_w
        state["cell_h"] = cell_h
        state["spacing"] = spacing
        state["rows"] = rows
        reshuffle(force=True)

    page.run_task(fallback_initial)

    data = view.data if isinstance(view.data, dict) else {}
    data["rebuild"] = lambda: coverwall_view(page)
    data["cover_year"] = state["year"]
    data["cover_folder"] = state["folder"]
    data["cover_size"] = state["size"]
    view.data = data
    return view
