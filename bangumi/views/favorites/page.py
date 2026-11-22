"""收藏首页：我的喜欢、自建收藏夹与新建入口。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.data.favorites import (
    DEFAULT_COLOR,
    FOLDER_COLORS,
    LIKES_ID,
    LIKES_NAME,
    NEW_FOLDER_COLOR,
    add_folder,
    folder_by_id,
    folder_colors,
    load_favorites,
    move_folder,
    remove_folder,
    save_favorites,
    update_folder,
)
from bangumi.ui.colors import background_color, foreground_color
from bangumi.ui.feedback import confirmation_dialog
from bangumi.ui.interaction import hover_icon
from bangumi.ui.layout import vertical_page
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import ui_text
from bangumi.views.favorites.fav_page import favorite_page_view
from bangumi.views.navigation import push_view
from bangumi.views.seasonlist.constants import ADD_COLOR
from bangumi.views.statistics.common.shared import _back_view


def open_folder_dialog(
    page: ft.Page,
    *,
    folder: dict | None = None,
    insert_index: int = 0,
    on_saved: Callable[[dict], None] | None = None,
) -> None:
    """新建或编辑收藏夹弹窗；保存后刷新首页并回调。"""
    data = load_favorites()
    editing = folder is not None
    fg = foreground_color(page)
    name_field = ft.TextField(
        label="收藏夹名称",
        value=str(folder.get("name") or "") if editing else "",
        text_size=14,
    )
    colors = list(FOLDER_COLORS)
    selected = {
        "color": str(folder.get("color") or DEFAULT_COLOR)
        if editing
        else DEFAULT_COLOR
    }
    if selected["color"] not in colors:
        selected["color"] = DEFAULT_COLOR

    swatches: list[ft.Container] = []

    def paint() -> None:
        for box, value in zip(swatches, colors):
            if value == DEFAULT_COLOR:
                box.bgcolor = background_color(page)
            else:
                box.bgcolor = value
            if value == selected["color"]:
                box.border = ft.Border.all(2, fg)
            elif value == DEFAULT_COLOR:
                box.border = ft.Border.all(1, fg)
            else:
                box.border = None
            try:
                box.update()
            except Exception:
                pass

    def pick(value: str):
        def handler(event: ft.ControlEvent) -> None:
            selected["color"] = value
            paint()

        return handler

    for value in colors:
        swatches.append(
            ft.Container(
                width=26,
                height=26,
                border_radius=5,
                bgcolor=(
                    background_color(page)
                    if value == DEFAULT_COLOR
                    else value
                ),
                on_click=pick(value),
            )
        )
    paint()

    def cancel(event: ft.ControlEvent) -> None:
        stop_resize()
        page.pop_dialog()

    def save(event: ft.ControlEvent) -> None:
        name = str(name_field.value or "").strip()
        if not name:
            name_field.error_text = "请输入名称"
            try:
                name_field.update()
            except Exception:
                pass
            return
        color = str(selected["color"])
        if editing and folder is not None:
            folder_id = str(folder.get("id") or "")
            update_folder(data, folder_id, name, color)
            saved = folder_by_id(data, folder_id) or {
                "id": folder_id,
                "name": name,
                "color": color,
                "items": [],
            }
        else:
            saved = add_folder(
                data,
                name,
                color,
                index=insert_index,
            )
        save_favorites(data)
        stop_resize()
        page.pop_dialog()
        if on_saved is not None:
            on_saved(saved)
        _refresh_favorites_home(page)

    content_box = ft.Container()
    palette = ft.Column(
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        width=26,
        controls=[],
    )
    palette_row = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[palette],
    )

    def layout_palette() -> None:
        """按窗口宽度重排色板，所有行左边缘对齐。"""
        dialog_width = min(
            360.0,
            max(220.0, float(page.width or 1000) * 0.8),
        )
        content_width = dialog_width - 48
        per_row = 1
        for candidate in (8, 4, 2, 1):
            need = candidate * 26 + (candidate - 1) * 8
            if content_width >= need:
                per_row = candidate
                break
        rows = [
            ft.Row(
                spacing=8,
                controls=swatches[index : index + per_row],
            )
            for index in range(0, len(swatches), per_row)
        ]
        palette.width = per_row * 26 + (per_row - 1) * 8
        palette.controls = rows
        # 弹窗内容实际宽度约为 dialog_width - 48。
        content_box.width = content_width
        name_field.width = content_width
        palette_row.width = content_width
        try:
            palette.update()
        except Exception:
            pass
        try:
            palette_row.update()
        except Exception:
            pass
        try:
            content_box.update()
        except Exception:
            pass

    content_box.content = ft.Column(
        tight=True,
        spacing=10,
        controls=[
            name_field,
            palette_row,
        ],
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text(
            "更改设置" if editing else "新建收藏夹"
        ),
        content=content_box,
        actions=[
            ft.Button(content=ui_text("取消"), on_click=cancel),
            ft.Button(
                content=ui_text("保存" if editing else "创建"),
                on_click=save,
            ),
        ],
    )
    layout_palette()

    # 弹窗打开期间跟随窗口宽度重排色板。
    previous_resize = page.on_resize
    active = {"value": True}

    def on_dialog_resize(event=None) -> None:
        if (
            previous_resize is not None
            and previous_resize is not on_dialog_resize
        ):
            previous_resize(event)
        if active["value"]:
            layout_palette()

    def stop_resize() -> None:
        active["value"] = False
        if page.on_resize is on_dialog_resize:
            page.on_resize = previous_resize

    page.on_resize = on_dialog_resize
    page.show_dialog(dialog)


def favorites_view(page: ft.Page) -> ft.View:
    """收藏首页。"""
    route = "/favorites"
    data = load_favorites()
    fg = foreground_color(page)
    compact = is_compact_layout(page)
    body = ft.Column(
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    hover_action_rows: list[ft.Row] = []

    def reset_hover_states() -> None:
        """收起残留的文件夹操作按钮。"""
        for row in hover_action_rows:
            if not row.visible:
                continue
            row.visible = False
            try:
                row.update()
            except Exception:
                pass

    def refresh() -> None:
        body.controls = build_buttons()
        try:
            body.update()
        except Exception:
            pass

    def open_folder(folder_id: str) -> None:
        reset_hover_states()
        push_view(page, favorite_page_view(page, folder_id))

    def set_actions(
        row: ft.Row,
        visible: bool,
    ) -> None:
        if row.visible == visible:
            return
        row.visible = visible
        try:
            row.update()
        except Exception:
            pass

    def folder_menu_items(
        index: int,
        folder: dict,
    ) -> list[ft.PopupMenuItem]:
        folder_id = str(folder.get("id") or "")
        folders = data.get("folders")
        total = len(folders) if isinstance(folders, list) else 0
        items: list[ft.PopupMenuItem] = []
        if index > 0:
            items.append(
                ft.PopupMenuItem(
                    icon=ft.Icons.MOVE_UP,
                    content=ui_text("上移"),
                    on_click=lambda event: (
                        move_folder(data, index, -1)
                        and (
                            save_favorites(data),
                            refresh(),
                        )
                    ),
                )
            )
        if index < total - 1:
            items.append(
                ft.PopupMenuItem(
                    icon=ft.Icons.MOVE_DOWN,
                    content=ui_text("下移"),
                    on_click=lambda event: (
                        move_folder(data, index, 1)
                        and (
                            save_favorites(data),
                            refresh(),
                        )
                    ),
                )
            )
        items.extend(
            [
                ft.PopupMenuItem(
                    icon=ft.Icons.SETTINGS,
                    content=ui_text("更改设置"),
                    on_click=lambda event, f=folder: (
                        open_folder_dialog(page, folder=f)
                    ),
                ),
                ft.PopupMenuItem(
                    icon=ft.Icons.PLAYLIST_ADD,
                    content=ui_text("在下方插入"),
                    on_click=lambda event, i=index: (
                        open_folder_dialog(
                            page,
                            insert_index=i + 1,
                        )
                    ),
                ),
                ft.PopupMenuItem(
                    icon=ft.Icons.DELETE,
                    content=ui_text("删除收藏夹"),
                    on_click=lambda event, f=folder: (
                        request_folder_delete(f)
                    ),
                ),
            ]
        )
        return items

    def request_folder_delete(folder: dict) -> None:
        folder_id = str(folder.get("id") or "")
        name = str(folder.get("name") or "")

        def confirm(inner: ft.ControlEvent) -> None:
            page.pop_dialog()
            if remove_folder(data, folder_id):
                save_favorites(data)
                refresh()

        page.show_dialog(
            confirmation_dialog(
                page,
                title="删除收藏夹",
                message=f"是否删除「{name}」？",
                confirm_label="删除",
                on_confirm=confirm,
            )
        )

    def folder_actions(index: int, folder: dict) -> list[ft.Control]:
        folder_id = str(folder.get("id") or "")
        folders = data.get("folders")
        total = len(folders) if isinstance(folders, list) else 0

        def move(delta: int) -> None:
            if move_folder(data, index, delta):
                save_favorites(data)
                refresh()

        def request_delete(event: ft.ControlEvent) -> None:
            name = str(folder.get("name") or "")

            def confirm(inner: ft.ControlEvent) -> None:
                page.pop_dialog()
                if remove_folder(data, folder_id):
                    save_favorites(data)
                    refresh()

            page.show_dialog(
                confirmation_dialog(
                    page,
                    title="删除收藏夹",
                    message=f"是否删除「{name}」？",
                    confirm_label="删除",
                    on_confirm=confirm,
                )
            )

        actions: list[ft.Control] = []
        if index > 0:
            actions.append(
                hover_icon(
                    page,
                    ft.Icons.MOVE_UP,
                    tooltip="上移",
                    on_click=lambda event: move(-1),
                    size=18,
                    padding=6,
                )
            )
        if index < total - 1:
            actions.append(
                hover_icon(
                    page,
                    ft.Icons.MOVE_DOWN,
                    tooltip="下移",
                    on_click=lambda event: move(1),
                    size=18,
                    padding=6,
                )
            )
        actions.extend(
            [
                hover_icon(
                    page,
                    ft.Icons.SETTINGS,
                    tooltip="更改设置",
                    on_click=lambda event, f=folder: (
                        open_folder_dialog(page, folder=f)
                    ),
                    size=18,
                    padding=6,
                ),
                hover_icon(
                    page,
                    ft.Icons.PLAYLIST_ADD,
                    tooltip="在下方插入",
                    on_click=lambda event, i=index: (
                        open_folder_dialog(
                            page,
                            insert_index=i + 1,
                        )
                    ),
                    size=18,
                    padding=6,
                ),
                hover_icon(
                    page,
                    ft.Icons.DELETE,
                    tooltip="删除收藏夹",
                    on_click=request_delete,
                    size=18,
                    padding=6,
                    color=ft.Colors.RED,
                ),
            ]
        )
        return actions

    def folder_button(folder: dict) -> ft.Button:
        folder_id = str(folder.get("id") or "")
        bg, text_color = folder_colors(
            page,
            str(folder.get("color") or ""),
        )
        button = ft.Button(
            content=ui_text(
                str(folder.get("name") or "未命名"),
                color=text_color,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            bgcolor=bg,
            expand=True,
            on_click=lambda event: open_folder(folder_id),
        )
        return button

    def folder_row(
        index: int,
        folder: dict,
    ) -> ft.Control:
        button = folder_button(folder)
        if compact:
            menu = ft.ContextMenu(
                expand=True,
                content=button,
                items=folder_menu_items(index, folder),
                primary_trigger=None,
                secondary_trigger=None,
                tertiary_trigger=None,
            )
            button.on_long_press = (
                lambda event: page.run_task(menu.open)
            )
            return ft.Container(expand=True, content=menu)

        actions = ft.Row(
            spacing=0,
            visible=False,
            controls=folder_actions(index, folder),
        )
        hover_action_rows.append(actions)
        return ft.Container(
            expand=True,
            content=ft.GestureDetector(
                on_enter=lambda event: set_actions(actions, True),
                on_exit=lambda event: set_actions(actions, False),
                content=ft.Row(
                    spacing=0,
                    controls=[button, actions],
                ),
            ),
        )

    def build_buttons() -> list[ft.Control]:
        controls: list[ft.Control] = [
            ft.Button(
                content=ui_text(
                    LIKES_NAME,
                    color=ft.Colors.WHITE,
                ),
                bgcolor=ADD_COLOR,
                on_click=lambda event: open_folder(LIKES_ID),
            )
        ]
        folders = data.get("folders")
        if isinstance(folders, list):
            for index, folder in enumerate(folders):
                if isinstance(folder, dict):
                    controls.append(folder_row(index, folder))
        controls.append(
            ft.Button(
                content=ui_text(
                    "新建收藏夹",
                    color=ft.Colors.WHITE,
                ),
                bgcolor=NEW_FOLDER_COLOR,
                on_click=lambda event: open_folder_dialog(page),
            )
        )
        return controls

    body.controls = build_buttons()
    view = _back_view(
        page,
        route=route,
        title="收藏",
        controls=[vertical_page([body], stretch=True)],
        rebuild=lambda: favorites_view(page),
    )
    data = view.data if isinstance(view.data, dict) else {}
    data["on_shown"] = reset_hover_states
    view.data = data
    return view


def _refresh_favorites_home(page: ft.Page) -> None:
    """收藏首页在栈中时重建其内容。"""
    for view in page.views:
        if str(getattr(view, "route", "")) == "/favorites":
            fresh = favorites_view(page)
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
