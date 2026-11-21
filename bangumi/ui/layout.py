"""页面布局与滚动辅助。"""

from __future__ import annotations

import flet as ft


def page_padding() -> ft.Padding:
    return ft.Padding.symmetric(horizontal=24, vertical=16)


# 右侧滚动条预留宽度。
SCROLLBAR_WIDTH = 26.0


def chart_width(
    page: ft.Page,
    default_width: float,
    *,
    # 16 为原安全边距，18 留给右侧滚动条。
    extra_right: float = SCROLLBAR_WIDTH + 16.0,
    min_width: float = 120.0,
) -> float:
    usable = float(page.width or 1000) - 48 - extra_right
    fitted = min(float(default_width), usable)
    if fitted >= min_width:
        return fitted
    # 极窄时允许低于 min_width，避免右侧被裁。
    return max(60.0, fitted)


def scroll_page(
    controls: list[ft.Control],
    *,
    spacing: int = 10,
) -> ft.Column:
    """用垂直与水平回退滚动包装页面内容。

    外层 Column 负责右侧垂直滚动条，内层
    Row 负责底部水平滚动条。两个滚动条始终可见，
    即使用户几乎不溢出也能发现它们。
    """
    content = ft.Column(spacing=spacing, controls=controls)
    return ft.Column(
        expand=True,
        scroll=ft.Scrollbar(
            orientation=ft.ScrollbarOrientation.RIGHT,
            thumb_visibility=True,
            track_visibility=True,
        ),
        controls=[
            ft.Row(
                scroll=ft.Scrollbar(
                    orientation=ft.ScrollbarOrientation.BOTTOM,
                    thumb_visibility=True,
                    track_visibility=True,
                ),
                controls=[content],
            )
        ],
    )


def vertical_page(
    controls: list[ft.Control],
    *,
    spacing: int = 10,
    stretch: bool = False,
) -> ft.Column:
    """用于需要受限宽度的内容的仅垂直页面包装。

    当页面依赖 ``ft.ResponsiveRow``（或任何需要
    受限宽度的控件）时使用；由于未插入水平 Row，
    内容会保持其受限宽度。
    """
    return ft.Column(
        expand=True,
        scroll=ft.Scrollbar(
            orientation=ft.ScrollbarOrientation.RIGHT,
            thumb_visibility=True,
            track_visibility=True,
        ),
        spacing=spacing,
        horizontal_alignment=(
            ft.CrossAxisAlignment.STRETCH
            if stretch
            else ft.CrossAxisAlignment.START
        ),
        controls=controls,
    )


def horizontal_strip(
    controls: list[ft.Control],
    *,
    spacing: int = 0,
    alignment: ft.MainAxisAlignment = ft.MainAxisAlignment.CENTER,
) -> ft.Row:
    """用于固定宽度或不换行行的水平滚动包装。"""
    return ft.Row(
        scroll=ft.ScrollMode.AUTO,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=alignment,
        spacing=spacing,
        controls=controls,
    )
