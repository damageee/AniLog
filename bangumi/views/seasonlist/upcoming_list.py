"""前瞻分类列表页。"""

from __future__ import annotations

import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover

from bangumi.ui.theme import ui_text
from bangumi.ui.constants import HOVER_ROW_OPACITY
from bangumi.ui.interaction import (
    back_icon,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.views.navigation import (
    go_back,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.widgets.toast import copy_text


class SeasonUpcomingListPage:
    """单个前瞻类别：可复制的动画标题。"""

    def __init__(
        self,
        page: ft.Page,
        label: str,
        titles: list[str],
    ) -> None:
        self.page = page
        self.view: ft.View | None = None

        def back(event: ft.ControlEvent) -> None:
            go_back(self.page, f"/season/upcoming/{label}")

        def make_row(name: str) -> ft.Container:
            foreground = foreground_color(self.page)
            row = ft.Container(
                content=ui_text(
                    name,
                    size=15,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                padding=ft.Padding.symmetric(
                    horizontal=6,
                    vertical=9,
                ),
                border_radius=6,
                border=ft.Border(
                    bottom=ft.BorderSide(
                        1,
                        ft.Colors.with_opacity(
                            0.1,
                            foreground,
                        ),
                    )
                ),
                tooltip="点击复制动画名称",
                on_click=(
                    lambda event, n=name: self.page.run_task(
                        copy_text,
                        self.page,
                        n,
                        "已复制动画名称",
                    )
                ),
            )
            row.animate = animation(
                120, ft.AnimationCurve.EASE_OUT
            )

            def on_hover(
                event: ft.ControlEvent,
                target: ft.Container = row,
            ) -> None:
                hovered = is_hover(event)
                target.bgcolor = (
                    ft.Colors.with_opacity(
                        HOVER_ROW_OPACITY, foreground
                    )
                    if hovered
                    else None
                )
                try:
                    target.update()
                except Exception:
                    pass

            row.on_hover = on_hover
            return row

        rows = [make_row(name) for name in titles]
        self.view = ft.View(
            route=f"/season/upcoming/{label}",
            appbar=ft.AppBar(
                title=ui_text(f"{label} —— 前瞻"),
                automatically_imply_leading=False,
                leading=back_icon(
                    self.page,
                    f"/season/upcoming/{label}",
                ),
            ),
            padding=page_padding(),
            controls=[
                vertical_page(
                    [
                        ft.Column(
                            spacing=0,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                            controls=rows,
                        )
                    ],
                    stretch=True,
                )
            ],
        )
        self.view.data = {
            "rebuild": lambda: SeasonUpcomingListPage(
                page, label, titles
            ).view
        }
