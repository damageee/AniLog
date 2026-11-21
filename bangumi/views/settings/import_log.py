"""设置页的上次自动填表记录。"""

from __future__ import annotations

import flet as ft
from bangumi.core.storage import (
    storage_directory,
)
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.interaction import (
    back_icon,
)
from bangumi.views.navigation import (
    push_view,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)


def _build_import_log_view(page: ft.Page) -> ft.View:
    view = ft.View(
        route="/settings/import-log",
        appbar=ft.AppBar(
            title=ui_text("上次自动填表记录"),
            leading=back_icon(page, "/settings/import-log"),
        ),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            scroll=ft.ScrollMode.AUTO,
                            controls=[
                                ui_text(
                                    _read_import_log_text(page),
                                    size=12,
                                    selectable=True,
                                )
                            ],
                        ),
                    )
                ]
            )
        ],
    )
    view.data = {
        "rebuild": lambda: _build_import_log_view(page)
    }
    return view


def _open_import_log(page: ft.Page) -> None:
    view = _build_import_log_view(page)
    if page.views and getattr(page.views[-1], "route", "") == view.route:
        return
    push_view(page, view)


def _read_import_log_text(page: ft.Page) -> str:
    path = storage_directory() / "import_log.txt"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        content = ""
    return content if content.strip() else "还没有导入记录"


