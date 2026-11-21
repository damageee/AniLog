"""设置页布局与按钮。"""

from __future__ import annotations

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.ui.colors import foreground_color
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.layout import (
    horizontal_strip,
    page_padding,
    vertical_page,
)
from bangumi.ui.interaction import back_icon
from bangumi.views.settings.advanced import open_advanced
from bangumi.views.settings.appearance import apply_theme
from bangumi.views.settings.export_data import export_app_data
from bangumi.views.settings.help import open_help
from bangumi.views.settings.import_data import start_import
from bangumi.views.settings.import_log import _open_import_log
from bangumi.views.settings.profile import (
    build_profile_block,
    handle_page_tap,
)
from bangumi.views.settings.sync import open_sync_dialog

THEME_BUTTON_WIDTH = 240
APP_VERSION_LABEL = "v2.0"


def settings_view(page: ft.Page) -> ft.View:
    preferences = Preferences.load()
    current_mode = (
        "Dark" if page.theme_mode == ft.ThemeMode.DARK else "Light"
    )
    secondary = ft.Colors.with_opacity(
        0.65, foreground_color(page)
    )
    theme_button = ft.Button(
        content=ui_text(current_mode, size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
    )
    help_button = ft.Button(
        content=ui_text("帮助", size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
        on_click=lambda event: open_help(page),
    )
    import_button = ft.Button(
        content=ui_text("导入应用数据", size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
        on_click=lambda event: start_import(page),
    )
    advanced_button = ft.Button(
        content=ui_text("高级", size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
        on_click=lambda event: open_advanced(page),
    )
    export_button = ft.Button(
        content=ui_text("导出应用数据", size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
        on_click=lambda event: page.run_task(export_app_data, page),
    )
    sync_button = ft.Button(
        content=ui_text("同步", size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
        on_click=lambda event: open_sync_dialog(page),
    )
    log_button = ft.Button(
        content=ui_text("上次自动填表记录", size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
        width=THEME_BUTTON_WIDTH,
        on_click=lambda event: _open_import_log(page),
    )

    def toggle_theme(event: ft.ControlEvent) -> None:
        apply_theme(page, preferences)

    theme_button.on_click = toggle_theme

    profile_block = build_profile_block(page)

    body = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        controls=[
            horizontal_strip(
                [
                    ft.Column(
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),
                        controls=[
                            profile_block,
                            ui_text(
                                APP_VERSION_LABEL,
                                size=12,
                                color=secondary,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            help_button,
                            theme_button,
                            advanced_button,
                            import_button,
                            export_button,
                            sync_button,
                            log_button,
                        ],
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
    )

    def on_page_tap(event: ft.ControlEvent) -> None:
        handle_page_tap(page)

    body = ft.GestureDetector(on_tap=on_page_tap, content=body)

    view = ft.View(
        route="/settings",
        appbar=ft.AppBar(
            title=ui_text("设置"),
            automatically_imply_leading=False,
            leading=back_icon(page, "/"),
        ),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.Row(
                        scroll=ft.Scrollbar(
                            orientation=ft.ScrollbarOrientation.BOTTOM,
                            thumb_visibility=True,
                            track_visibility=True,
                        ),
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=(
                            ft.CrossAxisAlignment.START
                        ),
                        controls=[body],
                    )
                ]
            )
        ],
    )
    view.data = {
        "rebuild": lambda: settings_view(page)
    }
    return view
