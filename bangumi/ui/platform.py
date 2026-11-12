"""平台类型判断。"""

from __future__ import annotations

import flet as ft


COMPACT_WIDTH = 600


def is_mobile(page: ft.Page) -> bool:
    return page.platform in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.ANDROID_TV,
        ft.PagePlatform.IOS,
    )


def is_compact(page: ft.Page) -> bool:
    width = page.width
    if not width:
        return False
    return float(width) < COMPACT_WIDTH


def is_android(page: ft.Page) -> bool:
    return page.platform in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.ANDROID_TV,
    )


def is_desktop(page: ft.Page) -> bool:
    return not is_mobile(page)


def is_compact_layout(page: ft.Page) -> bool:
    """窄屏或移动端：使用紧凑/移动布局。"""
    # 原来的判定：is_mobile(page) or is_compact(page)
    return is_compact(page)


def is_wide(page: ft.Page) -> bool:
    return not is_compact_layout(page)
