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


def _toast_colors(page: ft.Page) -> tuple[str, str]:
    if page.theme_mode == ft.ThemeMode.DARK:
        return ft.Colors.WHITE, ft.Colors.BLACK
    return ft.Colors.BLACK, ft.Colors.WHITE


def _show_toast(page: ft.Page, message: str) -> None:
    page_id = id(page)
    previous = _ACTIVE_TOASTS.get(page_id)
    if previous is not None and previous in page.overlay:
        page.overlay.remove(previous)

    token = _TOAST_TOKENS.get(page_id, 0) + 1
    _TOAST_TOKENS[page_id] = token

    background, text_color = _toast_colors(page)
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
        content=ft.Container(
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
        ),
    )
    page.overlay.append(toast)
    _ACTIVE_TOASTS[page_id] = toast
    page.update()
    toast.opacity = 1
    toast.update()
    page.run_task(_dismiss_toast, page, toast, token)


def show_toast(page: ft.Page, message: str) -> None:
    """轻量提示通知的公开包装。"""
    _show_toast(page, message)


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
