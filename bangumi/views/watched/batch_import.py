"""已阅页的批量导入对话框（Flet show_dialog 版）。"""

from __future__ import annotations

import asyncio

import flet as ft

from bangumi.services.bilibili_import import (
    BilibiliImportError,
    fetch_bilibili_following,
)
from bangumi.ui.colors import background_color, foreground_color
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import go_back, push_view
from bangumi.views.templates.append_from_text import (
    build_append_from_text_view,
)
from bangumi.views.watchlist.utils import (
    load_bilibili_uid,
    save_bilibili_uid,
)
from bangumi.views.widgets.toast import show_toast

BATCH_TEXT_ROUTE = "/watched/batch/text"


def _close_dialogs(page: ft.Page) -> None:
    """清空当前所有弹窗，避免叠加或跨页面残留。"""
    for _ in range(10):
        dialogs = getattr(page, "_dialogs", None)
        controls = (
            getattr(dialogs, "controls", None) if dialogs else None
        )
        if not controls:
            return
        try:
            page.pop_dialog()
        except Exception:
            return


def _split_titles(text: str) -> list[str]:
    return [
        line.strip()
        for line in str(text or "").splitlines()
        if line.strip()
    ]


def _content_width(page: ft.Page) -> float:
    """弹窗内容宽度：桌面 440，窄屏按比例收缩。"""
    return min(
        440.0,
        max(240.0, float(page.width or 400) * 0.82),
    )


def _dialog(page: ft.Page, title: str, controls: list[ft.Control]) -> ft.AlertDialog:
    return ft.AlertDialog(
        modal=True,
        bgcolor=background_color(page),
        title=ui_text(
            title,
            size=18,
            weight=ft.FontWeight.BOLD,
            color=foreground_color(page),
        ),
        content=ft.Container(
            width=_content_width(page),
            content=ft.Column(tight=True, spacing=10, controls=controls),
        ),
        actions=[],
    )


def _show_error(page: ft.Page, title: str, message: str) -> None:
    _close_dialogs(page)
    dialog = _dialog(
        page,
        title,
        [ui_text(message, color=foreground_color(page))],
    )
    dialog.actions = [
        ft.Button(
            content=ui_text("关闭"),
            on_click=lambda e: _close_dialogs(page),
        )
    ]
    page.show_dialog(dialog)


def open_batch_result_dialog(
    page: ft.Page,
    anime: dict[str, list[str]],
    on_confirm,
) -> None:
    """可编辑的分组结果弹窗；确认时回调 [(条目, 动画)]。"""
    _close_dialogs(page)

    rows_data: list[tuple[str, str]] = []
    for key, values in anime.items():
        for item in values:
            rows_data.append((key, item))
    if not rows_data:
        show_toast(page, "没有可导入的动画")
        return

    height = max(
        240.0,
        min(float(page.height or 800) * 0.6, 520.0),
    )
    column = ft.Column(
        spacing=6,
        height=height,
        scroll=ft.ScrollMode.AUTO,
    )
    column.controls.append(
        ft.Row(
            spacing=8,
            controls=[
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        "条目",
                        weight=ft.FontWeight.BOLD,
                        color=foreground_color(page),
                    ),
                ),
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        "动画",
                        weight=ft.FontWeight.BOLD,
                        color=foreground_color(page),
                    ),
                ),
                ft.Container(width=32),
            ],
        )
    )

    entries: list[dict[str, object]] = []

    def refresh_buttons() -> None:
        single = len(entries) <= 1
        for entry in entries:
            button = entry["button"]
            button.disabled = single
            button.icon_color = "#9CA3AF" if single else "#EF4444"

    def remove_row(entry: dict[str, object]) -> None:
        if len(entries) <= 1:
            return
        if entry in entries:
            entries.remove(entry)
        row = entry["row"]
        if row in column.controls:
            column.controls.remove(row)
        refresh_buttons()
        try:
            column.update()
        except Exception:
            pass

    for entry_text, anime_text in rows_data:
        entry_field = ft.TextField(value=entry_text, expand=1)
        anime_field = ft.TextField(value=anime_text, expand=1)
        data: dict[str, object] = {
            "entry": entry_field,
            "anime": anime_field,
        }
        button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color="#EF4444",
            tooltip="删除",
            on_click=lambda e, item=data: remove_row(item),
        )
        data["button"] = button
        row = ft.Row(
            spacing=8,
            controls=[
                entry_field,
                anime_field,
                ft.Container(width=32, content=button),
            ],
        )
        data["row"] = row
        entries.append(data)
        column.controls.append(row)

    refresh_buttons()

    def confirm(event=None) -> None:
        rows: list[tuple[str, str]] = []
        for data in entries:
            entry = str(data["entry"].value or "").strip()
            title = str(data["anime"].value or "").strip()
            if entry and title:
                rows.append((entry, title))
        _close_dialogs(page)
        on_confirm(rows)

    dialog = _dialog(
        page,
        "批量导入",
        [column],
    )
    dialog.actions = [
        ft.TextButton(
            content=ui_text("取消"),
            on_click=lambda e: _close_dialogs(page),
        ),
        ft.Button(
            content=ui_text("确定"),
            on_click=confirm,
        ),
    ]
    page.show_dialog(dialog)


def open_batch_import_dialog(page: ft.Page, on_titles) -> None:
    """三选一：从文本 / 从 Bilibili / 从 Bangumi（暂禁用）。"""
    fg = foreground_color(page)

    def open_uid() -> None:
        _close_dialogs(page)
        uid_field = ft.TextField(
            expand=True,
            height=40,
            value=load_bilibili_uid(),
            hint_text="请输入UID",
            input_filter=ft.NumbersOnlyInputFilter(),
            text_size=14,
            border_radius=8,
            content_padding=ft.Padding.symmetric(
                horizontal=12,
                vertical=8,
            ),
            text_vertical_align=ft.VerticalAlignment.CENTER,
        )
        error_text = ui_text(
            "",
            size=12,
            color=ft.Colors.RED,
            visible=False,
        )
        busy = {"value": False}
        # 导入范围：默认「看过」（仅 status=3），可切换为「全部」。
        scope = {"value": "watched"}

        def scope_style(selected: bool) -> ft.ButtonStyle:
            """选中态略深，未选中态白底细边框。"""
            return ft.ButtonStyle(
                shape=ft.StadiumBorder(),
                bgcolor="#E5E7EB" if selected else "#FFFFFF",
                color="#374151" if selected else fg,
                side=ft.BorderSide(
                    1,
                    "#D1D5DB" if selected else "#D8DEE6",
                ),
                padding=ft.Padding.symmetric(
                    horizontal=14, vertical=6
                ),
            )

        all_button: ft.Button
        watched_button: ft.Button

        def set_scope(value: str) -> None:
            scope["value"] = value
            all_button.style = scope_style(value == "all")
            watched_button.style = scope_style(value == "watched")
            # 仅刷新这两个按钮的样式。
            for button in (all_button, watched_button):
                try:
                    button.update()
                except Exception:
                    pass

        all_button = ft.Button(
            content=ui_text("全部", size=13),
            style=scope_style(False),
            on_click=lambda e: set_scope("all"),
        )
        watched_button = ft.Button(
            content=ui_text("看过", size=13),
            style=scope_style(True),
            on_click=lambda e: set_scope("watched"),
        )

        def confirm_uid(event=None) -> None:
            if busy["value"]:
                return
            uid = str(uid_field.value or "").strip()
            if not uid.isdigit():
                error_text.value = "请输入数字 UID"
                error_text.visible = True
                error_text.update()
                return
            save_bilibili_uid(uid)
            _close_dialogs(page)

            async def run() -> None:
                busy["value"] = True
                try:
                    statuses = (
                        {1, 2, 3}
                        if scope["value"] == "all"
                        else {3}
                    )
                    titles = await asyncio.to_thread(
                        fetch_bilibili_following, uid, statuses
                    )
                except BilibiliImportError as error:
                    _show_error(page, "导入失败", str(error))
                    return
                except Exception:
                    _show_error(page, "导入失败", "网络连接失败")
                    return
                finally:
                    busy["value"] = False
                show_toast(page, f"已获取 {len(titles)} 条")
                on_titles(titles)

            page.run_task(run)

        dialog = _dialog(
            page,
            "从 Bilibili 获取",
            [
                ft.Row(
                    [
                        ui_text("UID", weight=ft.FontWeight.BOLD),
                        uid_field,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ui_text("范围", weight=ft.FontWeight.BOLD),
                        all_button,
                        watched_button,
                    ],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                error_text,
            ],
        )
        dialog.actions = [
            ft.TextButton(
                content=ui_text("取消"),
                on_click=lambda e: _close_dialogs(page),
            ),
            ft.Button(
                content=ui_text("确定"),
                on_click=confirm_uid,
            ),
        ]
        page.show_dialog(dialog)

    def from_text(event=None) -> None:
        # 打开新页面前先清空所有弹窗。
        _close_dialogs(page)

        async def delayed() -> None:
            await asyncio.sleep(0.05)

            def confirm(text: str) -> None:
                titles = _split_titles(text)
                go_back(page, BATCH_TEXT_ROUTE)
                on_titles(titles)

            def cancel() -> None:
                go_back(page, BATCH_TEXT_ROUTE)

            push_view(
                page,
                build_append_from_text_view(
                    page,
                    "批量导入",
                    on_confirm=confirm,
                    on_cancel=cancel,
                    route=BATCH_TEXT_ROUTE,
                ),
            )

        page.run_task(delayed)

    def from_bilibili(event=None) -> None:
        # 打开 UID 弹窗前先清空所有弹窗。
        _close_dialogs(page)

        async def delayed() -> None:
            await asyncio.sleep(0.05)
            open_uid()

        page.run_task(delayed)

    content_w = _content_width(page)
    button_w = min(400.0, content_w - 32.0)
    dialog = _dialog(
        page,
        "批量导入",
        [
            ft.Button(
                content=ui_text("从文本"),
                width=button_w,
                on_click=from_text,
            ),
            ft.Button(
                content=ui_text("从 Bilibili"),
                width=button_w,
                on_click=from_bilibili,
            ),
            ft.Button(
                content=ui_text("从 Bangumi"),
                width=button_w,
                disabled=True,
            ),
        ],
    )
    dialog.actions = [
        ft.Button(
            content=ui_text("确定"),
            on_click=lambda e: _close_dialogs(page),
        )
    ]
    page.show_dialog(dialog)
