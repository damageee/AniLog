"""统计 —— 年度报告按钮列表页。"""

from __future__ import annotations

import flet as ft

from bangumi.data.dates import parse_iso_date
from bangumi.data.watched_data import load_records
from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import back_icon
from bangumi.ui.layout import page_padding, vertical_page
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.general.annual_report import open_annual_report


def annual_view(page: ft.Page) -> ft.View:
    """【年度报告】按钮列表页。"""
    route = "/statistics/annual"
    years: set[int] = set()
    for record in load_records():
        date = parse_iso_date(
            str(record.get("completion") or "")
        )
        if date is not None:
            years.add(date.year)

    def button(title: str) -> ft.Button:
        return ft.Button(
            content=ui_text(title, size=18),
            style=ft.ButtonStyle(
                text_style=ui_text_style(size=18)
            ),
            on_click=lambda event, name=title: open_annual_report(
                page, name
            ),
        )

    if years:
        buttons = [button("总览")]
        buttons.extend(
            button(str(year)) for year in sorted(years, reverse=True)
        )
        body: list[ft.Control] = [
            ft.Column(
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=buttons,
            )
        ]
    else:
        body = [
            ft.Column(
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ui_text(
                        "无记录",
                        size=12,
                        color=ft.Colors.with_opacity(
                            0.65,
                            foreground_color(page),
                        ),
                    )
                ],
            )
        ]
    view = ft.View(
        route=route,
        appbar=ft.AppBar(
            title=ui_text("年度报告"),
            automatically_imply_leading=False,
            leading=back_icon(page, "/statistics"),
        ),
        padding=page_padding(),
        controls=[vertical_page(body)],
    )
    view.data = {"rebuild": lambda: annual_view(page)}
    return view
