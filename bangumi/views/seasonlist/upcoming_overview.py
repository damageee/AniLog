"""前瞻总览页。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.colors import foreground_color
from bangumi.ui.theme import ui_text
from bangumi.views.navigation import (
    push_view,
)
from bangumi.views.seasonlist.upcoming_list import (
    SeasonUpcomingListPage,
)
from bangumi.views.seasonlist.utils import apply_label_counts
from bangumi.views.templates.button_list import (
    build_button_list_view,
)


class SeasonUpcomingPage:
    """前瞻 page: one full-width button per upcoming category."""

    def __init__(
        self,
        page: ft.Page,
        categories: dict[str, list[str]],
    ) -> None:
        self.page = page
        self.categories = categories
        self._category_buttons: list[
            tuple[ft.Button, str, int]
        ] = []
        buttons: list[tuple[str, Callable]] = []
        for label, names in categories.items():
            buttons.append(
                (
                    label,
                    (
                        lambda event, name=label, titles=names: (
                            self._open_category(name, titles)
                        )
                    ),
                )
            )
        self.view = build_button_list_view(
            page,
            title="前瞻",
            route="/season/upcoming",
            buttons=buttons,
            rebuild=lambda: SeasonUpcomingPage(
                page, categories
            ).view,
            on_long_press=self._show_counts,
            on_long_press_end=self._hide_counts,
            on_long_press_cancel=self._hide_counts,
            footer=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ui_text(
                        "长按空白处显示数量",
                        size=11,
                        color=ft.Colors.with_opacity(
                            0.55,
                            foreground_color(page),
                        ),
                    )
                ],
            ),
        )
        holder = self.view.controls[0]
        column = getattr(holder, "content", holder)
        for button, (label, names) in zip(
            getattr(column, "controls", []),
            categories.items(),
        ):
            self._category_buttons.append(
                (button, label, len(names))
            )

    def _show_counts(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        apply_label_counts(self._category_buttons, True, self.page)

    def _hide_counts(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        apply_label_counts(self._category_buttons, False, self.page)

    def _open_category(
        self,
        label: str,
        titles: list[str],
    ) -> None:
        category = SeasonUpcomingListPage(
            self.page,
            label,
            titles,
        )
        push_view(self.page, category.view)
