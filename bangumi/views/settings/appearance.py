"""设置页的主题切换。"""

from __future__ import annotations

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.ui.colors import background_color


def apply_theme(page: ft.Page, preferences: Preferences) -> None:
    dark = page.theme_mode != ft.ThemeMode.DARK
    page.theme_mode = (
        ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    )
    page.bgcolor = background_color(page)
    preferences.theme_mode = "dark" if dark else "light"
    preferences.save()
    # 路由变更守卫在顶层视图已匹配 page.route 时会跳过重建。
    # 清空视图栈会强制首页与当前页按新主题颜色
    # 重新创建。
    page.views.clear()
    if page.on_route_change is not None:
        page.on_route_change(None)
    else:
        page.update()
