"""自动填表入口。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.feedback import close_dialog
from bangumi.data.watched_data import save_records
from bangumi.views.watched.fill_table.constants import INTRO_LINES, POWER_OPTIONS
from bangumi.views.watched.fill_table.runner import _start_fill


def open_fill_dialog(owner: "WatchedPage") -> None:
    page = owner.page
    power_dropdown = ft.Dropdown(
        value="loose",
        width=280,
        options=[
            ft.DropdownOption(key=key, text=label)
            for key, label in POWER_OPTIONS
        ],
    )
    rename_checkbox = ft.Checkbox(
        label=ui_text(
            "用导入的动画名覆盖原名称（旧名称可在修改时查看）"
        ),
        value=False,
    )
    force_checkbox = ft.Checkbox(
        label=ui_text("强制覆盖（包括已有内容与封面图）"),
        value=False,
    )
    mark_checkbox = ft.Checkbox(
        label=ui_text("导入后自动标记不再导入该条"),
        value=True,
    )

    def _mark_all(value: bool) -> None:
        for record in owner.records:
            record["skip_fill"] = value
        save_records(owner.records)

    def _confirm_mark(value: bool) -> None:
        text = (
            "确定要标记所有行吗？"
            if value
            else "确定要清除所有行的标记吗？"
        )
        confirm = ft.AlertDialog(
            modal=True,
            title=ui_text("确认操作"),
            content=ui_text(text),
            actions=[],
        )

        def cancel(event: ft.ControlEvent) -> None:
            page.pop_dialog()

        def ok(event: ft.ControlEvent) -> None:
            page.pop_dialog()
            _mark_all(value)

        confirm.actions = [
            ft.TextButton(content=ui_text("取消"), on_click=cancel),
            ft.Button(content=ui_text("确定"), on_click=ok),
        ]
        page.show_dialog(confirm)

    def _confirm_cover_only() -> None:
        confirm = ft.AlertDialog(
            modal=True,
            title=ui_text("确认操作"),
            content=ui_text(
                "要无视「不自动导入」直接导入所有封面图吗"
            ),
            actions=[],
        )

        def no(event: ft.ControlEvent) -> None:
            page.pop_dialog()
            _start_from_dialog(
                owner,
                dialog,
                power_dropdown,
                rename_checkbox,
                force_checkbox,
                mark_checkbox,
                with_covers=True,
                covers_only=True,
                ignore_skip=False,
            )

        def yes(event: ft.ControlEvent) -> None:
            page.pop_dialog()
            _start_from_dialog(
                owner,
                dialog,
                power_dropdown,
                rename_checkbox,
                force_checkbox,
                mark_checkbox,
                with_covers=True,
                covers_only=True,
                ignore_skip=True,
            )

        confirm.actions = [
            ft.TextButton(content=ui_text("否"), on_click=no),
            ft.Button(content=ui_text("是"), on_click=yes),
        ]
        page.show_dialog(confirm)

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("从Bangumi填充表格"),
        content=ft.Column(
            tight=True,
            spacing=10,
            controls=[
                *[ui_text(line, size=13) for line in INTRO_LINES],
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ui_text("你可以选择我的决定权大小：", size=13),
                        power_dropdown,
                    ],
                ),
                rename_checkbox,
                force_checkbox,
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        mark_checkbox,
                        ft.TextButton(
                            content=ui_text("标记所有"),
                            on_click=lambda event: _confirm_mark(True),
                        ),
                        ft.TextButton(
                            content=ui_text("全部取标"),
                            on_click=lambda event: _confirm_mark(False),
                        ),
                    ],
                ),
                ui_text(
                    "要继续吗？导入时要导入动画封面图吗？",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
        ),
        actions=[
            ft.TextButton(
                content=ui_text("取消"),
                on_click=lambda event: close_dialog(dialog),
            ),
            ft.TextButton(
                content=ui_text("仅文本"),
                on_click=lambda event: _start_from_dialog(
                    owner,
                    dialog,
                    power_dropdown,
                    rename_checkbox,
                    force_checkbox,
                    mark_checkbox,
                    with_covers=False,
                ),
            ),
            ft.TextButton(
                content=ui_text("仅封面"),
                on_click=lambda event: _confirm_cover_only(),
            ),
            ft.TextButton(
                content=ui_text("我全都要"),
                on_click=lambda event: _start_from_dialog(
                    owner,
                    dialog,
                    power_dropdown,
                    rename_checkbox,
                    force_checkbox,
                    mark_checkbox,
                    with_covers=True,
                ),
            ),
        ],
    )
    page.show_dialog(dialog)


def _start_from_dialog(
    owner: "WatchedPage",
    dialog: ft.AlertDialog,
    power_dropdown: ft.Dropdown,
    rename_checkbox: ft.Checkbox,
    force_checkbox: ft.Checkbox,
    mark_checkbox: ft.Checkbox,
    *,
    with_covers: bool,
    covers_only: bool = False,
    ignore_skip: bool = False,
) -> None:
    power = str(power_dropdown.value or "loose")
    rename = bool(rename_checkbox.value)
    force = bool(force_checkbox.value)
    mark_done = bool(mark_checkbox.value)
    close_dialog(dialog)
    _start_fill(
        owner,
        with_covers=with_covers,
        covers_only=covers_only,
        ignore_skip=ignore_skip,
        power=power,
        rename=rename,
        force=force,
        mark_done=mark_done,
    )


