"""制作人员（班底）入口页。"""

from __future__ import annotations

import flet as ft

from bangumi.data.watched_data import (
    Record,
    load_records,
    normalize_staff,
    staff_items,
)
from bangumi.ui.layout import vertical_page
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.templates.page_shell import make_view


def _staff_keys(records: list[Record]) -> list[str]:
    """收集所有记录出现过的 STAFF 职务名，按 STAFF_ORDER 排序。"""
    keys = {
        key
        for record in records
        for key in normalize_staff(record.get("staff"))
    }
    # 复用 staff_items 的排序规则（STAFF_ORDER + 特殊作画监督 + 未知职务）。
    ordered = staff_items({key: "占位" for key in keys})
    return [key for key, _ in ordered]


def staff_view(page: ft.Page) -> ft.View:
    """制作人员列表：每个职务一个按钮。"""
    records = load_records()

    def open_search(key: str) -> None:
        # 延迟导入，避免与统计包产生循环引用。
        from bangumi.views.general.staff_search import (
            open_staff_key_search,
        )

        open_staff_key_search(page, records, key)

    buttons = [
        ft.Button(
            content=ui_text(key, size=18),
            style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
            on_click=lambda event, k=key: open_search(k),
        )
        for key in _staff_keys(records)
    ]
    if not buttons:
        buttons = [ui_text("暂无 STAFF 数据", size=13)]
    return make_view(
        page,
        route="/statistics/staff",
        title="制作人员",
        controls=[
            vertical_page(
                [
                    ft.Column(
                        spacing=12,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.STRETCH
                        ),
                        controls=buttons,
                    )
                ]
            )
        ],
        rebuild=lambda: staff_view(page),
        back=True,
        scroll=False,
    )
