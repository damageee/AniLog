"""剪贴板辅助函数与轻量提示通知。"""

from __future__ import annotations

import asyncio

import flet as ft
from bangumi.ui.anim import animation

from bangumi.ui.theme import ui_text
from bangumi.ui.interaction import hover_copy

TOAST_FADE_SECONDS = 0.18
TOAST_HOLD_SECONDS = 1.6
TOAST_BOTTOM = 24
_TOAST_TOKENS: dict[int, int] = {}
_ACTIVE_TOASTS: dict[int, ft.Container] = {}


def ensure_clipboard(page: ft.Page) -> ft.Clipboard:
    for service in page.services:
        if isinstance(service, ft.Clipboard):
            return service
    clipboard = ft.Clipboard()
    page.services.append(clipboard)
    return clipboard


def _toast_colors(
    page: ft.Page,
    error: bool = False,
) -> tuple[str, str]:
    if error:
        return "#DC2626", ft.Colors.WHITE
    if page.theme_mode == ft.ThemeMode.DARK:
        return ft.Colors.WHITE, ft.Colors.BLACK
    return ft.Colors.BLACK, ft.Colors.WHITE


def _show_toast(
    page: ft.Page,
    message: str,
    *,
    error: bool = False,
) -> None:
    page_id = id(page)
    previous = _ACTIVE_TOASTS.get(page_id)
    if previous is not None and previous in page.overlay:
        page.overlay.remove(previous)

    token = _TOAST_TOKENS.get(page_id, 0) + 1
    _TOAST_TOKENS[page_id] = token

    background, text_color = _toast_colors(page, error)
    bubble = ft.Container(
        bgcolor=background,
        border_radius=8,
        padding=ft.Padding.symmetric(
            horizontal=18,
            vertical=10,
        ),
        content=ui_text(
            message,
            size=14,
            color=text_color,
            text_align=ft.TextAlign.CENTER,
        ),
        offset=ft.Offset(0, 0),
        animate_offset=animation(
            60,
            ft.AnimationCurve.EASE_IN_OUT,
        ),
    )
    toast = ft.Container(
        left=0,
        right=0,
        bottom=TOAST_BOTTOM,
        alignment=ft.Alignment.CENTER,
        opacity=0,
        animate_opacity=animation(
            int(TOAST_FADE_SECONDS * 1000),
            ft.AnimationCurve.EASE_OUT,
        ),
        content=bubble,
    )
    page.overlay.append(toast)
    _ACTIVE_TOASTS[page_id] = toast
    page.update()
    toast.opacity = 1
    toast.update()
    if error:
        # 错误提示出现后左右抖动。
        page.run_task(_shake_toast, page, toast, bubble, token)
    page.run_task(_dismiss_toast, page, toast, token)


async def _shake_toast(
    page: ft.Page,
    toast: ft.Container,
    bubble: ft.Container,
    token: int,
) -> None:
    """左右抖动；新 toast 顶替时立即停止。"""
    offsets = (0.02, -0.02, 0.016, -0.016, 0.010, -0.010, 0.0)
    for value in offsets:
        if _TOAST_TOKENS.get(id(page)) != token:
            return
        bubble.offset = ft.Offset(value, 0)
        try:
            bubble.update()
        except Exception:
            return
        await asyncio.sleep(0.05)


def show_toast(
    page: ft.Page,
    message: str,
    *,
    error: bool = False,
) -> None:
    """轻量提示通知的公开包装。"""
    _show_toast(page, message, error=error)


async def _dismiss_toast(
    page: ft.Page,
    toast: ft.Container,
    token: int,
) -> None:
    await asyncio.sleep(TOAST_HOLD_SECONDS)
    if _TOAST_TOKENS.get(id(page)) != token:
        return
    toast.opacity = 0
    try:
        toast.update()
    except Exception:
        page.update()
    await asyncio.sleep(TOAST_FADE_SECONDS)
    if _TOAST_TOKENS.get(id(page)) != token:
        return
    if toast in page.overlay:
        page.overlay.remove(toast)
    if _ACTIVE_TOASTS.get(id(page)) is toast:
        _ACTIVE_TOASTS.pop(id(page), None)
    page.update()


async def copy_text(
    page: ft.Page,
    text: str,
    message: str,
) -> None:
    clipboard = ensure_clipboard(page)
    await clipboard.set(text)
    _show_toast(page, message)


def copyable_title(page: ft.Page, text: str) -> ft.Container:
    def on_click(event: ft.ControlEvent) -> None:
        page.run_task(
            copy_text,
            page,
            text,
            "已复制标题文本到剪贴板",
        )

    return hover_copy(
        page,
        ui_text(
            text,
            no_wrap=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        on_click,
    )
