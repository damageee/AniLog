"""追季主页。"""

from __future__ import annotations

import asyncio
import datetime as dt

import flet as ft

from bangumi.data.season_data import (
    add_quarter,
    load_quarters,
)
from bangumi.services.season_scraper import fetch_future_categories
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.interaction import back_icon
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.navigation import (
    push_view,
)
from bangumi.ui.feedback import (
    show_error_dialog,
)
from bangumi.data.quarter_core import quarter_label
from bangumi.views.seasonlist.constants import (
    ADD_COLOR,
    SEASONS,
    UPCOMING_COLOR,
    YEAR_AHEAD,
    YEAR_START,
)
from bangumi.views.seasonlist.season_target import SeasonTargetPage
from bangumi.views.seasonlist.upcoming_overview import SeasonUpcomingPage
from bangumi.views.seasonlist.utils import (
    apply_label_counts,
    current_season,
    hide_loading,
    quarter_counts,
    show_loading,
)
from bangumi.views.widgets.progress_bar import (
    build_progress_bar,
    build_stats_row,
)


class SeasonPage:
    """Owns the 追季 page and its local quarter state."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.quarters: list[dict] = []
        self._quarter_buttons: list[tuple] = []
        self._upcoming_loading = False
        self._upcoming_ring = None
        self.upcoming_button: ft.Button | None = None
        self.body = ft.Column(
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[],
        )
        self.view = ft.View(
            route="/season",
            appbar=ft.AppBar(
                title=ui_text("追季"),
                automatically_imply_leading=False,
                leading=back_icon(self.page, "/"),
            ),
            padding=page_padding(),
            controls=[
                ft.GestureDetector(
                    expand=True,
                    content=vertical_page([self.body], stretch=True),
                    on_long_press=self._show_counts,
                    on_long_press_end=self._hide_counts,
                    on_long_press_cancel=self._hide_counts,
                )
            ],
        )
        self.view.data = {
            "rebuild": lambda: SeasonPage(page).view
        }
        self.refresh()

    def refresh(self) -> None:
        self.quarters = load_quarters()
        done = 0
        total = 0
        for quarter in self.quarters:
            quarter_done, quarter_total = quarter_counts(quarter)
            done += quarter_done
            total += quarter_total
        self.body.controls = [
            build_stats_row(done, total),
            build_progress_bar(self.page, done, total),
            self._quarter_list(),
            self._add_button(),
            ft.Column(
                spacing=24,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self._upcoming_button(),
                    ft.GestureDetector(
                        on_tap=lambda event: None,
                        on_long_press=lambda event: None,
                        on_long_press_end=lambda event: None,
                        on_long_press_cancel=lambda event: None,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ui_text(
                                    "长按空白处显示数量",
                                    size=11,
                                    color=ft.Colors.with_opacity(
                                        0.55,
                                        foreground_color(self.page),
                                    ),
                                )
                            ],
                        ),
                    ),
                ],
            ),
        ]

    def _quarter_list(self) -> ft.Column:
        buttons: list[ft.Control] = []
        self._quarter_buttons = []
        for quarter in self.quarters:
            year = int(quarter["year"])
            index = int(quarter["quarter"])
            label = quarter_label(year, index)
            done, total = quarter_counts(quarter)
            button = ft.Button(
                content=ui_text(label),
                on_click=(
                    lambda event, y=year, i=index: (
                        self._open_target(y, i)
                    )
                ),
            )
            self._quarter_buttons.append((button, label, done, total))
            buttons.append(button)
        return ft.Column(
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=buttons,
        )

    def _show_counts(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        apply_label_counts(self._quarter_buttons, True, self.page)

    def _hide_counts(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        apply_label_counts(self._quarter_buttons, False, self.page)

    def _add_button(self) -> ft.Button:
        return ft.Button(
            content=ui_text("添加季度", color=ft.Colors.WHITE),
            bgcolor=ADD_COLOR,
            on_click=self._open_add,
        )

    def _upcoming_button(self) -> ft.Button:
        button = ft.Button(
            content=ui_text("前瞻", color=ft.Colors.WHITE),
            bgcolor=UPCOMING_COLOR,
            disabled=self._upcoming_loading,
            on_click=self._start_upcoming,
        )
        self.upcoming_button = button
        return button

    def _start_upcoming(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        if self._upcoming_loading:
            return
        self._upcoming_loading = True
        if self.upcoming_button is not None:
            self.upcoming_button.disabled = True
            self.upcoming_button.update()
        self._upcoming_ring = show_loading(self.page)
        self.page.run_task(self._run_upcoming)

    async def _run_upcoming(self) -> None:
        categories = None
        ring = self._upcoming_ring
        self._upcoming_ring = None
        try:
            try:
                categories = await asyncio.to_thread(
                    fetch_future_categories
                )
            except Exception:
                categories = None
        finally:
            hide_loading(self.page, ring)
        self._upcoming_loading = False
        if self.upcoming_button is not None:
            self.upcoming_button.disabled = False
        visible = self.view in self.page.views
        if visible and self.upcoming_button is not None:
            self.upcoming_button.update()
        if not visible:
            return
        if categories is None:
            show_error_dialog(
                self.page,
                title="前瞻",
                message="坠机了",
            )
            return
        future = SeasonUpcomingPage(self.page, categories)
        push_view(self.page, future.view)

    def _open_target(self, year: int, index: int) -> None:
        target = SeasonTargetPage(
            self.page,
            year,
            index,
            on_deleted=self.refresh,
            on_changed=self.refresh,
        )
        push_view(self.page, target.view)

    def _open_add(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        foreground = foreground_color(self.page)
        today = dt.date.today()
        current_year = today.year
        season_index = current_season()
        years = list(
            range(YEAR_START, current_year + YEAR_AHEAD + 1)
        )
        header = ui_text(
            "",
            size=18,
            weight=ft.FontWeight.BOLD,
            color=foreground,
        )

        picker = ft.CupertinoPicker(
            controls=[ui_text(str(year), size=18) for year in years],
            item_extent=36,
            selected_index=current_year - YEAR_START,
            width=200,
            height=150,
            on_change=lambda event: update_header(),
        )
        dropdown = ft.Dropdown(
            width=160,
            value=SEASONS[season_index],
            options=[
                ft.dropdown.Option(key=name, text=name)
                for name in SEASONS
            ],
            on_select=lambda event: update_header(),
        )

        def selected_year() -> int:
            index = picker.selected_index
            if 0 <= index < len(years):
                return years[index]
            return current_year

        def selected_season() -> int:
            value = dropdown.value
            if value in SEASONS:
                return SEASONS.index(value)
            return season_index

        def update_header() -> None:
            header.value = (
                f"{selected_year()}年"
                f"{SEASONS[selected_season()]}季度"
            )
            try:
                header.update()
            except RuntimeError:
                pass
            except Exception:
                pass

        update_header()

        def cancel(event: ft.ControlEvent) -> None:
            self.page.pop_dialog()

        def confirm(event: ft.ControlEvent) -> None:
            year = selected_year()
            index = selected_season()
            try:
                created = add_quarter(year, index)
            except Exception:
                created = False
            self.page.pop_dialog()
            if created:
                self.refresh()
            self.page.update()
            self._show_message(
                "创建成功"
                if created
                else "创建失败（该季度已存在）"
            )

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=background_color(self.page),
                title=ui_text(
                    "添加季度",
                    weight=ft.FontWeight.BOLD,
                    color=foreground,
                ),
                title_text_style=ui_text_style(
                    color=foreground,
                    weight=ft.FontWeight.BOLD,
                ),
                content_text_style=ui_text_style(color=foreground),
                content=ft.Container(
                    width=320,
                    content=ft.Column(
                        tight=True,
                        spacing=12,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),
                        controls=[
                            header,
                            picker,
                            ft.Row(
                                [
                                    ui_text("季度"),
                                    dropdown,
                                ],
                                spacing=8,
                                alignment=(
                                    ft.MainAxisAlignment.CENTER
                                ),
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

    def _show_message(self, message: str) -> None:
        foreground = foreground_color(self.page)

        def close(event: ft.ControlEvent) -> None:
            self.page.pop_dialog()

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=background_color(self.page),
                title=ui_text(
                    "提示",
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


def season_view(page: ft.Page) -> ft.View:
    return SeasonPage(page).view
