"""年×季度统计页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.feedback import (
    no_records_note,
)
from bangumi.ui.layout import (
    page_padding,
    scroll_page,
)
from bangumi.views.navigation import QUARTER_WORKS
from bangumi.views.navigation import open_detail
from bangumi.data.quarter_core import (
    first_month,
    quarter_label,
    quarter_of_broadcast,
)
from bangumi.data.watched_data import (
    Record,
    is_tv_specification,
    load_records,
)


class QuarterPage:
    """按开播年份和季度对放送区间记录分组。"""

    def __init__(
        self,
        page: ft.Page,
        records: list[Record],
        route: str,
    ) -> None:
        self.page = page
        self.records = records
        prev_toggles: dict = {}
        if page.views:
            top = page.views[-1]
            if (
                str(getattr(top, "route", "")) == route
                and isinstance(getattr(top, "data", None), dict)
            ):
                prev_toggles = dict(
                    top.data.get("chart_toggles") or {}
                )
        self.chart_toggles = {
            "counts": bool(prev_toggles.get("counts", False)),
        }
        show_counts = self.chart_toggles["counts"]
        grouped: dict[tuple[int, int], list[Record]] = {}
        for record in records:
            text = str(record.get("broadcast", "") or "")
            if "~" not in text and "～" not in text:
                continue
            if not is_tv_specification(
                str(record.get("specification", "") or "")
            ):
                continue
            target = quarter_of_broadcast(text)
            if target is None:
                continue
            grouped.setdefault(target, []).append(record)

        self.groups = sorted(
            grouped.items(),
            key=lambda item: (item[0][0], item[0][1]),
        )
        self.buttons: list[tuple[ft.Button, str, int, int, int]] = []
        year_buttons: dict[int, list[ft.Control]] = {}
        for (year, quarter_index), group in self.groups:
            label = quarter_label(year, quarter_index)
            button = ft.Button(
                content=ui_text(
                    f"{label} ({len(group)})"
                    if show_counts
                    else label
                ),
                on_click=(
                    lambda event, y=year, q=quarter_index: (
                        self._open_quarter(y, q)
                    )
                ),
            )
            self.buttons.append(
                (button, label, len(group), year, quarter_index)
            )
            year_buttons.setdefault(year, []).append(button)

        self.count_checkbox = ft.Checkbox(
            label=ui_text("显示数量"),
            value=show_counts,
            on_change=self._toggle_counts,
        )
        content: list[ft.Control] = []
        if year_buttons:
            content.append(self.count_checkbox)
            content.append(
                ft.Column(
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Row(
                            spacing=8,
                            alignment=ft.MainAxisAlignment.START,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                            controls=year_buttons[year],
                        )
                        for year in sorted(year_buttons)
                    ],
                )
            )
        else:
            content.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        no_records_note(
                            self.page,
                            height=60,
                            width=max(
                                200.0,
                                float(self.page.width or 1000) - 48,
                            ),
                        )
                    ],
                )
            )

        self.view = ft.View(
            route=route,
            appbar=ft.AppBar(title=ui_text("年×季度")),
            padding=page_padding(),
            controls=[scroll_page(content)],
        )
        self.view.data = {
            "rebuild": lambda: build_quarter_view(
                page, load_records(), {}, route
            ),
            "chart_toggles": self.chart_toggles,
        }

    def _open_quarter(self, year: int, index: int) -> None:
        synthetic = {
            "broadcast": f"{year}年{first_month(index)}月1日",
        }
        open_detail(
            self.page,
            self.records,
            synthetic,
            QUARTER_WORKS,
        )

    def _toggle_counts(self, event: ft.ControlEvent) -> None:
        show = bool(event.control.value)
        self.chart_toggles["counts"] = show
        for button, label, count, _, _ in self.buttons:
            button.content.value = (
                f"{label} ({count})" if show else label
            )
        try:
            self.page.update(
                *(button for button, _, _, _, _ in self.buttons)
            )
        except Exception:
            self.page.update()


def build_quarter_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    view = QuarterPage(page, records, route).view
    view_data = view.data if isinstance(view.data, dict) else {}
    view_data["rebuild"] = lambda: build_quarter_view(
        page, load_records(), clicked, route
    )
    view.data = view_data
    return view
