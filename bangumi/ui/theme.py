"""字体、文本辅助函数与 Material 主题。"""

from __future__ import annotations

import flet as ft

# 页面启动时从本地资源注册字体族。
UI_FONT = "Bangumi Consolas"
UI_FONT_BOLD = "Bangumi Consolas Bold"
SIMSUN_FONT = "Bangumi SimSun"
FONT_ASSETS = {
    UI_FONT: "/fonts/consola.ttf",
    UI_FONT_BOLD: "/fonts/consolab.ttf",
    SIMSUN_FONT: "/fonts/simsun_proc.ttf",
}
SYSTEM_FONT_FALLBACK = [
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "SimSun",
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "PingFang SC",
    "Hiragino Sans GB",
    "WenQuanYi Micro Hei",
    "Arial Unicode MS",
    "Segoe UI Emoji",
    "Segoe UI",
    "Arial",
    "sans-serif",
]
UI_FONT_FALLBACK = [SIMSUN_FONT, *SYSTEM_FONT_FALLBACK]

# 统计文案对所有文字都使用内置的宋体字体。
STATS_FONT = SIMSUN_FONT

TITLE_SIZE = 40
BROWN_PERIOD = "#8B4512"


def ui_text_style(font_family: str = UI_FONT, **kwargs) -> ft.TextStyle:
    return ft.TextStyle(
        font_family=font_family,
        font_family_fallback=UI_FONT_FALLBACK,
        **kwargs,
    )


def stats_text_style(**kwargs) -> ft.TextStyle:
    kwargs.setdefault("font_family_fallback", UI_FONT_FALLBACK)
    return ft.TextStyle(
        font_family=STATS_FONT,
        **kwargs,
    )


def ui_text(value: str = "", **kwargs) -> ft.Text:
    kwargs.setdefault("font_family", UI_FONT)
    kwargs.setdefault("font_family_fallback", UI_FONT_FALLBACK)
    return ft.Text(value, **kwargs)


def stats_text(value: str = "", **kwargs) -> ft.Text:
    kwargs.setdefault("font_family_fallback", UI_FONT_FALLBACK)
    return ft.Text(
        value,
        font_family=STATS_FONT,
        **kwargs,
    )


def app_theme(*, dark: bool = False) -> ft.Theme:
    background_color = ft.Colors.BLACK if dark else ft.Colors.WHITE
    text_color = ft.Colors.WHITE if dark else ft.Colors.BLACK
    style = ui_text_style(color=text_color)
    return ft.Theme(
        font_family=UI_FONT,
        color_scheme_seed=ft.Colors.BLUE_GREY,
        color_scheme=ft.ColorScheme(
            surface=background_color,
            surface_bright=background_color,
            surface_container=background_color,
            surface_container_high=background_color,
            surface_container_highest=background_color,
            surface_container_low=background_color,
            surface_container_lowest=background_color,
            surface_dim=background_color,
            on_surface=text_color,
            on_surface_variant=text_color,
        ),
        system_overlay_style=ft.SystemOverlayStyle(
            status_bar_color=ft.Colors.TRANSPARENT,
            system_navigation_bar_color=ft.Colors.TRANSPARENT,
            system_navigation_bar_divider_color=ft.Colors.TRANSPARENT,
            status_bar_icon_brightness=(
                ft.Brightness.LIGHT if dark else ft.Brightness.DARK
            ),
            system_navigation_bar_icon_brightness=(
                ft.Brightness.LIGHT if dark else ft.Brightness.DARK
            ),
            enforce_system_status_bar_contrast=False,
            enforce_system_navigation_bar_contrast=False,
        ),
        appbar_theme=ft.AppBarTheme(
            color=text_color,
            bgcolor=background_color,
            title_text_style=style,
            toolbar_text_style=style,
        ),
        text_theme=ft.TextTheme(
            body_large=style,
            body_medium=style,
            body_small=style,
            display_large=style,
            display_medium=style,
            display_small=style,
            headline_large=style,
            headline_medium=style,
            headline_small=style,
            label_large=style,
            label_medium=style,
            label_small=style,
            title_large=style,
            title_medium=style,
            title_small=style,
        ),
    )
