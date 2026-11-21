"""加入收藏夹弹窗：选择目标收藏夹并追加条目。"""

from __future__ import annotations

import flet as ft

from bangumi.data.favorites import (
    LIKES_ID,
    add_item,
    folder_colors,
    load_favorites,
    save_favorites,
)
from bangumi.data.watched_data import Record, record_title
from bangumi.ui.colors import foreground_color
from bangumi.ui.theme import ui_text
from bangumi.views.favorites.page import open_folder_dialog
from bangumi.views.seasonlist.constants import ADD_COLOR


def open_add_to_favorites_dialog(
    page: ft.Page,
    record: Record,
) -> None:
    """弹出收藏夹列表，将记录追加到选中的收藏夹。"""
    data = load_favorites()
    uid = str(record.get("uid") or "").strip()
    name = record_title(record) or str(
        record.get("anime") or ""
    )

    def contains(items: list) -> bool:
        if not uid:
            return False
        return any(
            str(item.get("uid") or "") == uid
            for item in items
            if isinstance(item, dict)
        )

    def add_to(folder_id: str) -> None:
        # 重新读取，避免用旧副本覆盖其它改动。
        fresh = load_favorites()
        add_item(fresh, folder_id, uid, name)
        save_favorites(fresh)
        page.pop_dialog()

    def create_folder(event: ft.ControlEvent) -> None:
        def saved(folder: dict) -> None:
            folder_id = str(folder.get("id") or "")
            if not folder_id:
                return
            # 重新读取，拿到刚保存的收藏夹再追加。
            fresh = load_favorites()
            add_item(fresh, folder_id, uid, name)
            save_favorites(fresh)
            page.pop_dialog()

        open_folder_dialog(
            page,
            insert_index=0,
            on_saved=saved,
        )

    likes_items = data.get("likes")
    if not isinstance(likes_items, list):
        likes_items = []

    fg = foreground_color(page)
    disabled_bg = ft.Colors.with_opacity(0.12, fg)
    disabled_fg = ft.Colors.with_opacity(0.45, fg)
    likes_disabled = contains(likes_items)

    buttons: list[ft.Control] = [
        ft.Button(
            content=ui_text(
                "新建收藏夹",
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.GREEN,
            on_click=create_folder,
        ),
        ft.Button(
            content=ui_text(
                "我的喜欢",
                color=(
                    disabled_fg
                    if likes_disabled
                    else ft.Colors.WHITE
                ),
            ),
            bgcolor=(
                disabled_bg if likes_disabled else ADD_COLOR
            ),
            disabled=likes_disabled,
            on_click=lambda event: add_to(LIKES_ID),
        ),
    ]

    folders = data.get("folders")
    if isinstance(folders, list):
        for folder in folders:
            if not isinstance(folder, dict):
                continue
            folder_id = str(folder.get("id") or "")
            bg, text_color = folder_colors(
                page,
                str(folder.get("color") or ""),
            )
            items = folder.get("items")
            disabled = contains(
                items if isinstance(items, list) else []
            )
            buttons.append(
                ft.Button(
                    content=ui_text(
                        str(folder.get("name") or "未命名"),
                        color=(
                            disabled_fg
                            if disabled
                            else text_color
                        ),
                    ),
                    bgcolor=(
                        disabled_bg if disabled else bg
                    ),
                    disabled=disabled,
                    on_click=(
                        lambda event, fid=folder_id: add_to(fid)
                    ),
                )
            )

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ui_text("加入收藏夹"),
            content=ft.Container(
                height=float(page.height or 800) * 2 / 3,
                width=min(
                    360.0,
                    float(page.width or 1000) * 0.8,
                ),
                content=ft.Column(
                    scroll=ft.Scrollbar(
                        orientation=ft.ScrollbarOrientation.RIGHT,
                        thumb_visibility=True,
                        track_visibility=True,
                    ),
                    spacing=8,
                    horizontal_alignment=(
                        ft.CrossAxisAlignment.STRETCH
                    ),
                    controls=buttons,
                ),
            ),
            actions=[
                ft.Button(
                    content=ui_text("取消"),
                    on_click=lambda event: page.pop_dialog(),
                )
            ],
        )
    )
