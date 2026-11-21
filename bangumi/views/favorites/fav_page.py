"""收藏夹页：条目列表、拖动排序与搜索添加。"""

from __future__ import annotations

import flet as ft

from bangumi.data.favorites import (
    LIKES_ID,
    LIKES_NAME,
    add_item,
    folder_by_id,
    load_favorites,
    move_item,
    record_by_uid,
    remove_item,
    save_favorites,
)
from bangumi.data.watched_data import load_records, record_title
from bangumi.ui.colors import foreground_color
from bangumi.ui.events import is_hover
from bangumi.ui.feedback import confirmation_dialog
from bangumi.ui.interaction import hover_icon
from bangumi.ui.layout import vertical_page
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import ui_text
from bangumi.views.general.virtual_search import virtual_search_page
from bangumi.views.navigation import ENTRY, open_detail, push_view
from bangumi.views.seasonlist.constants import ADD_COLOR
from bangumi.views.statistics.common.shared import _back_view


def favorite_page_view(page: ft.Page, folder_id: str) -> ft.View:
    """打开某个收藏夹（likes 为「我的喜欢」）。"""
    route = f"/favorites/{folder_id}"
    data = load_favorites()
    folder = folder_by_id(data, folder_id)
    title = LIKES_NAME
    if folder_id != LIKES_ID:
        title = (
            str(folder.get("name") or "")
            if isinstance(folder, dict)
            else "收藏夹"
        )
    records = load_records()
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.65, fg)
    compact = is_compact_layout(page)
    body = ft.Column(
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    def set_actions(row: ft.Row, visible: bool) -> None:
        if row.visible == visible:
            return
        row.visible = visible
        try:
            row.update()
        except Exception:
            pass

    def action_icon(
        icon,
        tooltip: str,
        handler,
        *,
        color: str | None = None,
    ) -> ft.Control:
        return hover_icon(
            page,
            icon,
            tooltip=tooltip,
            on_click=handler,
            size=18,
            padding=6,
            color=color,
        )

    def move_at(index: int, delta: int) -> None:
        if move_item(data, folder_id, index, delta):
            save_favorites(data)
            refresh()

    def remove_at(index: int) -> None:
        if remove_item(data, folder_id, index):
            save_favorites(data)
            refresh()

    def request_missing_delete(index: int) -> None:
        def confirm(inner: ft.ControlEvent) -> None:
            page.pop_dialog()
            remove_at(index)

        page.show_dialog(
            confirmation_dialog(
                page,
                title="记录已不存在",
                message="原记录已不存在，是否从收藏夹中删除？",
                confirm_label="删除",
                on_confirm=confirm,
            )
        )

    def refresh_favorite_view() -> None:
        """搜索添加后刷新收藏夹视图。"""
        for view in page.views:
            if str(getattr(view, "route", "")) == route:
                fresh = favorite_page_view(page, folder_id)
                view.controls = fresh.controls
                view.appbar = fresh.appbar
                view.data = fresh.data
                try:
                    page.update(view)
                except Exception:
                    try:
                        page.update()
                    except Exception:
                        pass
                return
        refresh()

    def open_search(index: int) -> None:
        route_search = f"/favorites/{folder_id}/search/{index}"
        current = folder_by_id(data, folder_id)
        folder_items = (
            current.get("items")
            if isinstance(current, dict)
            else []
        )
        # 只按非空 uid 过滤，已收藏的动画不再出现在搜索结果里。
        existing = {
            str(item.get("uid") or "")
            for item in (
                folder_items
                if isinstance(folder_items, list)
                else []
            )
            if str(item.get("uid") or "")
        }
        rows = [
            (record_title(record), record)
            for record in records
            if str(record.get("uid") or "") not in existing
        ]

        def add_from_row(item, query: str) -> None:
            record = item[1]
            add_item(
                data,
                folder_id,
                str(record.get("uid") or ""),
                record_title(record),
                index=None if index < 0 else index,
            )
            save_favorites(data)
            if (
                page.views
                and str(getattr(page.views[-1], "route", ""))
                == route_search
            ):
                page.views.pop()
                try:
                    page.update()
                except Exception:
                    pass
            refresh_favorite_view()

        def row_builder(item, query: str) -> ft.Control:
            name = str(item[0])
            row = ft.Container(
                height=40,
                padding=ft.Padding.symmetric(horizontal=8),
                border_radius=6,
                alignment=ft.Alignment.CENTER_LEFT,
                content=ui_text(
                    name,
                    size=14,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            )

            def on_hover(event: ft.ControlEvent) -> None:
                row.bgcolor = (
                    ft.Colors.with_opacity(0.06, fg)
                    if is_hover(event)
                    else None
                )
                try:
                    row.update()
                except Exception:
                    pass

            row.on_hover = on_hover
            row.on_click = (
                lambda event, it=item: add_from_row(it, query)
            )
            return row

        def build(query: str) -> ft.View:
            return virtual_search_page(
                page,
                title="添加收藏",
                route=route_search,
                hint_text="搜索动画",
                all_rows=rows,
                row_builder=row_builder,
                initial_query=query,
                rebuild=build,
            )

        push_view(page, build(""))

    def item_menu_items(
        index: int,
        total: int,
    ) -> list[ft.PopupMenuItem]:
        items: list[ft.PopupMenuItem] = []
        if index > 0:
            items.append(
                ft.PopupMenuItem(
                    icon=ft.Icons.MOVE_UP,
                    content=ui_text("上移"),
                    on_click=lambda event: move_at(index, -1),
                )
            )
        if index < total - 1:
            items.append(
                ft.PopupMenuItem(
                    icon=ft.Icons.MOVE_DOWN,
                    content=ui_text("下移"),
                    on_click=lambda event: move_at(index, 1),
                )
            )
        items.extend(
            [
                ft.PopupMenuItem(
                    icon=ft.Icons.PLAYLIST_ADD,
                    content=ui_text("在上方插入"),
                    on_click=lambda event: open_search(index),
                ),
                ft.PopupMenuItem(
                    icon=ft.Icons.DELETE,
                    content=ui_text("删除收藏"),
                    on_click=lambda event: remove_at(index),
                ),
            ]
        )
        return items

    def item_row(
        index: int,
        item: dict,
        total: int,
    ) -> ft.Control:
        uid = str(item.get("uid") or "")
        stored_name = str(item.get("name") or "")
        record = record_by_uid(records, uid)
        exists = record is not None
        display = (
            record_title(record)
            if exists
            else f"{stored_name or uid}（原记录已不存在）"
        )
        name_button = ft.Button(
            content=ui_text(
                display,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            expand=True,
        )

        def open_item(event: ft.ControlEvent) -> None:
            if record is not None:
                open_detail(page, records, record, ENTRY)
                return
            request_missing_delete(index)

        name_button.on_click = open_item

        if compact:
            menu = ft.ContextMenu(
                expand=True,
                content=name_button,
                items=item_menu_items(index, total),
                primary_trigger=None,
                secondary_trigger=None,
                tertiary_trigger=None,
            )
            name_button.on_long_press = (
                lambda event: page.run_task(menu.open)
            )
            return ft.Container(expand=True, content=menu)

        actions_list: list[ft.Control] = []
        if index > 0:
            actions_list.append(
                action_icon(
                    ft.Icons.MOVE_UP,
                    "上移",
                    lambda event: move_at(index, -1),
                )
            )
        if index < total - 1:
            actions_list.append(
                action_icon(
                    ft.Icons.MOVE_DOWN,
                    "下移",
                    lambda event: move_at(index, 1),
                )
            )
        actions_list.extend(
            [
                action_icon(
                    ft.Icons.PLAYLIST_ADD,
                    "在上方插入",
                    lambda event: open_search(index),
                ),
                action_icon(
                    ft.Icons.DELETE,
                    "删除收藏",
                    lambda event: remove_at(index),
                    color=ft.Colors.RED,
                ),
            ]
        )
        actions = ft.Row(
            spacing=0,
            visible=False,
            controls=actions_list,
        )
        return ft.Container(
            expand=True,
            content=ft.GestureDetector(
                on_enter=lambda event: set_actions(actions, True),
                on_exit=lambda event: set_actions(actions, False),
                content=ft.Row(
                    spacing=0,
                    controls=[name_button, actions],
                ),
            ),
        )

    def add_button() -> ft.Control:
        return ft.Button(
            content=ui_text(
                "添加收藏",
                color=ft.Colors.WHITE,
            ),
            bgcolor=ADD_COLOR,
            on_click=lambda event: open_search(-1),
        )

    def rebuild() -> None:
        current = folder_by_id(data, folder_id)
        items = (
            current.get("items")
            if isinstance(current, dict)
            else []
        )
        controls: list[ft.Control] = []
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    controls.append(
                        item_row(index, item, len(items))
                    )
        if not controls:
            controls.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ui_text(
                            "暂无收藏",
                            size=12,
                            color=secondary,
                        )
                    ],
                )
            )
        controls.append(add_button())
        body.controls = controls

    def refresh() -> None:
        rebuild()
        try:
            body.update()
        except Exception:
            pass

    rebuild()
    return _back_view(
        page,
        route=route,
        title=title,
        controls=[vertical_page([body], stretch=True)],
        rebuild=lambda: favorite_page_view(page, folder_id),
    )
