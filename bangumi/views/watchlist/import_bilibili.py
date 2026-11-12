"""Bilibili 在看追番导入。"""

from __future__ import annotations

import flet as ft

from bangumi.services.proxy import http_get
from bangumi.ui.colors import background_color, foreground_color
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.watchlist.constants import (
    BILIBILI_FOLLOW_URL,
    BILIBILI_HEADERS,
    BILIBILI_PAGE_SIZE,
    BILIBILI_TIMEOUT,
)
from bangumi.views.watchlist.utils import (
    clean_bilibili_title,
    has_animation_style,
    load_bilibili_uid,
)


class BilibiliImportError(Exception):
    """面向用户的 Bilibili 导入失败。"""


def fetch_bilibili_watching(uid: str) -> list[str]:
    """Return the user's 在看 bangumi + anime dramas (read-only)."""
    titles: list[str] = []
    seen: set[str] = set()
    headers = dict(BILIBILI_HEADERS)
    headers["Referer"] = (
        f"https://space.bilibili.com/{uid}/bangumi"
    )
    for follow_type, anime_only in ((1, False), (2, True)):
        pn = 1
        while True:
            response = http_get(
                BILIBILI_FOLLOW_URL,
                params={
                    "type": follow_type,
                    "follow_status": 0,
                    "pn": pn,
                    "ps": BILIBILI_PAGE_SIZE,
                    "vmid": uid,
                },
                headers=headers,
                timeout=BILIBILI_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            code = payload.get("code")
            data = payload.get("data")
            if code == -400:
                raise BilibiliImportError(
                    "UID 格式不正确或请求失败"
                )
            if code == 53013:
                raise BilibiliImportError(
                    "用户不存在或追番列表未公开"
                )
            if code != 0:
                raise BilibiliImportError(
                    str(payload.get("message") or "导入失败")
                )
            if not data:
                raise BilibiliImportError(
                    "用户不存在或追番列表未公开"
                )

            total = int(data.get("total") or 0)
            items = data.get("list") or []
            if not items:
                break
            for item in items:
                if item.get("follow_status") != 2:
                    continue
                if anime_only and not has_animation_style(item):
                    continue
                title = clean_bilibili_title(item.get("title"))
                if not title or title in seen:
                    continue
                seen.add(title)
                titles.append(title)

            if total <= 0 or pn * BILIBILI_PAGE_SIZE >= total:
                break
            pn += 1
    return titles


def open_bilibili_import(page: ft.Page, on_import) -> None:
    foreground = foreground_color(page)
    uid_field = ft.TextField(
        width=180,
        height=40,
        value=load_bilibili_uid(),
        hint_text="请输入UID",
        input_filter=ft.NumbersOnlyInputFilter(),
        text_size=14,
        border_radius=8,
        content_padding=ft.Padding.symmetric(
            horizontal=10,
            vertical=8,
        ),
    )
    error_text = ui_text(
        "",
        size=12,
        color=ft.Colors.RED,
        visible=False,
    )
    target = {"high": False}
    toggle = ft.Button(content=ui_text("低优先级"))

    def toggle_target(event: ft.ControlEvent) -> None:
        target["high"] = not target["high"]
        toggle.content = ui_text(
            "高优先级" if target["high"] else "低优先级"
        )
        toggle.update()

    toggle.on_click = toggle_target

    def confirm(event: ft.ControlEvent) -> None:
        uid = (uid_field.value or "").strip()
        if not uid:
            error_text.value = "请输入UID"
            error_text.visible = True
            error_text.update()
            return
        half = "high" if target["high"] else "low"
        page.pop_dialog()
        page.run_task(on_import, uid, half)

    def cancel(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text(
                "导入Bilibili在看追番",
                weight=ft.FontWeight.BOLD,
                color=foreground,
            ),
            title_text_style=ui_text_style(
                color=foreground,
                weight=ft.FontWeight.BOLD,
            ),
            content_text_style=ui_text_style(color=foreground),
            content=ft.Container(
                width=360,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Row(
                            [
                                ui_text("UID"),
                                uid_field,
                            ],
                            spacing=12,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                        ),
                        error_text,
                        ft.Row(
                            [
                                ui_text("导入至"),
                                toggle,
                            ],
                            spacing=12,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.Button(
                    content=ui_text("取消"),
                    on_click=cancel,
                ),
                ft.Button(
                    content=ui_text(
                        "确认",
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.BLUE,
                    on_click=confirm,
                ),
            ],
        )
    )


def show_import_result(
    page: ft.Page,
    title: str,
    message: str,
) -> None:
    foreground = foreground_color(page)

    def close(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text(
                title,
                weight=ft.FontWeight.BOLD,
                color=foreground,
            ),
            title_text_style=ui_text_style(
                color=foreground,
                weight=ft.FontWeight.BOLD,
            ),
            content=ui_text(message, color=foreground),
            content_text_style=ui_text_style(color=foreground),
            actions=[
                ft.Button(
                    content=ui_text("关闭"),
                    on_click=close,
                ),
            ],
        )
    )
