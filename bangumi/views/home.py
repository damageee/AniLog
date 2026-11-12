"""首页与主分区列表。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import (
    BROWN_PERIOD,
    TITLE_SIZE,
    UI_FONT_BOLD,
    ui_text,
    ui_text_style,
)
from bangumi.views.navigation.catalog import SECTION_PAGES
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    horizontal_strip,
)

SECTIONS: tuple[tuple[str, str], ...] = tuple(
    (page.label, page.route)
    for page in SECTION_PAGES
    if page.route not in ("/", "/settings")
)


HOME_BUTTON_HEIGHT = 48.0
HOME_SPACING = 12.0
HOME_TITLE_HEIGHT = 52.0
HOME_SETTINGS_HEIGHT = 48.0
HOME_PAGE_PADDING = 20.0


def home_view(page: ft.Page) -> ft.View:
    holder: dict[str, ft.View] = {}
    mobile = is_compact_layout(page)
    top = HOME_PAGE_PADDING + (HOME_SPACING if mobile else 0)

    def build_controls() -> list[ft.Control]:
        return _home_controls(page)

    view = ft.View(
        route="/",
        padding=ft.Padding.only(
            left=24,
            top=top,
            right=24,
            bottom=HOME_PAGE_PADDING,
        ),
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=build_controls(),
    )
    holder["view"] = view

    previous_resize = page.on_resize

    def on_resize(event: ft.ControlEvent | None = None) -> None:
        current = holder.get("view")
        if current is not None and current in page.views:
            current.controls = build_controls()
            try:
                page.update()
            except RuntimeError:
                return
        if previous_resize is not None and previous_resize is not on_resize:
            previous_resize(event)

    page.on_resize = on_resize
    return view


def _home_controls(page: ft.Page) -> list[ft.Control]:
    buttons = [
        _navigation_button(
            page,
            label=name,
            route=route,
            size=18,
        )
        for name, route in SECTIONS
    ]
    title = horizontal_strip(
        [
            ft.Icon(
                icon=ft.Icons.BEACH_ACCESS,
                size=TITLE_SIZE,
                color="#2EA7E0",
            ),
            _home_title(page),
        ],
        spacing=9,
        alignment=ft.MainAxisAlignment.START,
    )
    settings = _navigation_button(
        page,
        label="设置",
        route="/settings",
        size=18,
    )

    button_block = (
        len(buttons) * HOME_BUTTON_HEIGHT
        + max(0, len(buttons) - 1) * HOME_SPACING
    )
    needed = (
        HOME_TITLE_HEIGHT
        + HOME_SPACING * 2
        + button_block
        + HOME_SETTINGS_HEIGHT
    )
    available = (
        (page.height or 800) - HOME_PAGE_PADDING * 2
    )
    mobile = is_compact_layout(page)

    if not mobile and needed <= available:
        return [
            title,
            ft.Container(height=HOME_SPACING),
            ft.Column(
                expand=True,
                spacing=HOME_SPACING,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=buttons,
            ),
            settings,
        ]

    return [
        ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.Scrollbar(
                orientation=ft.ScrollbarOrientation.RIGHT,
                thumb_visibility=True,
                track_visibility=True,
            ),
            controls=[
                ft.Column(
                    spacing=HOME_SPACING,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[title, *buttons, settings],
                )
            ],
        )
    ]


def _home_title(page: ft.Page) -> ft.Text:
    title_style = ui_text_style(
        font_family=UI_FONT_BOLD,
        size=TITLE_SIZE,
        weight=ft.FontWeight.NORMAL,
        color=foreground_color(page),
    )
    return ft.Text(
        spans=[
            ft.TextSpan("Bangumi", style=title_style),
            ft.TextSpan(
                ".",
                style=ui_text_style(
                    font_family=UI_FONT_BOLD,
                    size=TITLE_SIZE,
                    weight=ft.FontWeight.NORMAL,
                    color=BROWN_PERIOD,
                ),
            ),
        ],
    )


def _go(page: ft.Page, route: str) -> None:
    from bangumi.views.navigation.stack import request_push_route

    request_push_route(page, route)


def _navigation_button(
    page: ft.Page,
    *,
    label: str,
    route: str,
    size: int,
) -> ft.Button:
    return ft.Button(
        content=ui_text(label, size=size),
        style=ft.ButtonStyle(text_style=ui_text_style(size=size)),
        on_click=lambda event: _go(page, route),
    )
