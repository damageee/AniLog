"""大图预览弹窗。"""

from __future__ import annotations

import asyncio

import flet as ft
from bangumi.ui.anim import animation

from bangumi.services.image_clipboard import copy_image_bytes
from bangumi.ui.images import preview_image_size
from bangumi.ui.platform import is_mobile
from bangumi.ui.theme import ui_text
from bangumi.ui.interaction import (
    hover_zoom,
)

_PREVIEW_TOKENS: dict[int, int] = {}


def show_image_preview(
    page: ft.Page,
    data: bytes,
    *,
    title: str = "封面图",
    max_width: float = 520.0,
) -> None:
    w, h = preview_image_size(data, page, max_width=max_width)
    image = ft.Image(
        src=data,
        width=w,
        height=h,
        fit=ft.BoxFit.CONTAIN,
    )
    image_box = hover_zoom(page, image, scale=1.05)
    image_box.width = w
    image_box.height = h
    if not is_mobile(page):
        image_box.tooltip = "点击复制图片到剪贴板"

    toast_text = ui_text("", size=12, color=ft.Colors.WHITE)
    toast = ft.Container(
        left=0,
        right=0,
        bottom=10,
        alignment=ft.Alignment.CENTER,
        opacity=0,
        animate_opacity=animation(
            150, ft.AnimationCurve.EASE_OUT
        ),
        content=ft.Container(
            bgcolor=ft.Colors.with_opacity(0.82, ft.Colors.BLACK),
            border_radius=8,
            padding=ft.Padding.symmetric(
                horizontal=14,
                vertical=8,
            ),
            content=toast_text,
        ),
    )

    async def show_toast(message: str) -> None:
        token = _PREVIEW_TOKENS.get(id(page), 0) + 1
        _PREVIEW_TOKENS[id(page)] = token
        toast_text.value = message
        toast.opacity = 1
        try:
            page.update()
        except Exception:
            pass
        await asyncio.sleep(1.2)
        if _PREVIEW_TOKENS.get(id(page)) != token:
            return
        toast.opacity = 0
        try:
            page.update()
        except Exception:
            pass

    async def copy(event=None) -> None:
        ok = await asyncio.to_thread(copy_image_bytes, data)
        await show_toast(
            "图片已复制到剪贴板" if ok else "复制失败"
        )

    if not is_mobile(page):
        image_box.on_click = lambda event: page.run_task(copy)

    stack = ft.Stack(
        width=w,
        height=h,
        clip_behavior=ft.ClipBehavior.NONE,
        controls=[image_box, toast],
    )
    page.show_dialog(
        ft.AlertDialog(
            title=ui_text(title),
            content=stack,
            actions=[
                ft.Button(
                    content=ui_text("关闭"),
                    on_click=lambda event: page.pop_dialog(),
                )
            ],
        )
    )
