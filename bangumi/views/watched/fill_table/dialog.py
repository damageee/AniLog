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
    dialog_width = min(
        460.0,
        max(240.0, float(page.width or 400) - 96.0),
    )
    content_w = max(200.0, dialog_width - 48.0)  # 扣除弹窗左右内边距
    content_h = min(float(page.height or 800) * 0.62, 560.0)
    power_width = max(160.0, min(220.0, content_w))
    # 决定权：自定义胶囊单选，显示当前选项原文。
    power_state = {"value": "loose"}
    power_get = lambda: power_state["value"]
    power_text = dict(POWER_OPTIONS)
    power_menu_label = ui_text(
        power_text.get(power_state["value"], ""),
        size=12,
    )
    power_panel = ft.Container(
        visible=False,
        width=power_width,
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#E5E8EE"),
        border_radius=8,
        padding=ft.Padding.all(6),
        content=ft.Column(spacing=0, controls=[]),
    )

    def rebuild_power_menu() -> None:
        rows: list[ft.Control] = []
        for key, _label in POWER_OPTIONS:
            tick = ft.Icon(
                ft.Icons.CHECK,
                size=16,
                visible=key == power_state["value"],
            )
            rows.append(
                ft.Container(
                    height=36,
                    on_click=lambda e, k=key: pick_power(k),
                    content=ft.Row(
                        spacing=4,
                        controls=[
                            ft.Container(width=24, content=tick),
                            ui_text(_label, size=13),
                        ],
                    ),
                )
            )
        power_panel.content.controls = rows
        try:
            power_panel.update()
        except Exception:
            pass

    def pick_power(key: str) -> None:
        power_state["value"] = key
        power_menu_label.value = power_text.get(key, key)
        try:
            power_menu_label.update()
        except Exception:
            pass
        power_panel.visible = False
        rebuild_power_menu()
        try:
            power_panel.update()
        except Exception:
            pass

    def toggle_power(event=None) -> None:
        power_panel.visible = not power_panel.visible
        rebuild_power_menu()
        try:
            power_panel.update()
        except Exception:
            pass

    power_trigger = ft.Container(
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#E5E8EE"),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        on_click=toggle_power,
        content=ft.Row(
            spacing=8,
            controls=[
                power_menu_label,
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18),
            ],
        ),
    )
    rename_checkbox = ft.Checkbox(value=False)
    force_checkbox = ft.Checkbox(value=False)
    mark_checkbox = ft.Checkbox(value=True)
    ignore_skip_checkbox = ft.Checkbox(value=False)

    def check_row(box: ft.Checkbox, text: str) -> ft.Row:
        return ft.Row(
            spacing=6,
            width=content_w,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                box,
                ft.Container(
                    expand=True,
                    content=ui_text(text, size=13, no_wrap=False),
                ),
            ],
        )

    rename_row = check_row(
        rename_checkbox,
        "用导入的动画名覆盖原名称（旧名称可在修改时查看）",
    )
    force_row = check_row(
        force_checkbox,
        "强制覆盖（包括已有内容与封面图）",
    )
    mark_row = check_row(
        mark_checkbox,
        "导入后自动标记不再导入该条",
    )
    ignore_skip_row = check_row(
        ignore_skip_checkbox,
        "无视「不自动导入」标记",
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

    power_block: ft.Control = ft.Column(
        spacing=6,
        width=content_w,
        controls=[
            ft.Row(
                spacing=10,
                wrap=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ui_text("你可以选择我的决定权大小：", size=13),
                    power_trigger,
                ],
            ),
            power_panel,
        ],
    )
    rebuild_power_menu()

    mark_border = (
        ft.Colors.with_opacity(0.25, ft.Colors.WHITE)
        if page.theme_mode == ft.ThemeMode.DARK
        else "#D8DEE6"
    )
    mark_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=8),
        side=ft.BorderSide(1, mark_border),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("从 Bangumi 填充表格"),
        content=ft.Container(
            width=content_w,
            content=ft.Column(
                tight=True,
                spacing=10,
                width=content_w,
                height=content_h,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    *[
                        ui_text(
                            line,
                            size=13,
                            width=content_w,
                            no_wrap=False,
                        )
                        for line in INTRO_LINES
                    ],
                    power_block,
                    rename_row,
                    force_row,
                    mark_row,
                    ft.Row(
                        spacing=8,
                        width=content_w,
                        controls=[
                            ft.TextButton(
                                content=ft.Container(
                                    alignment=ft.Alignment.CENTER,
                                    content=ui_text(
                                        "标记所有",
                                        no_wrap=True,
                                        max_lines=1,
                                    ),
                                ),
                                expand=1,
                                style=mark_style,
                                on_click=lambda event: _confirm_mark(True),
                            ),
                            ft.TextButton(
                                content=ft.Container(
                                    alignment=ft.Alignment.CENTER,
                                    content=ui_text(
                                        "全部取标",
                                        no_wrap=True,
                                        max_lines=1,
                                    ),
                                ),
                                expand=1,
                                style=mark_style,
                                on_click=lambda event: _confirm_mark(False),
                            ),
                        ],
                    ),
                    ignore_skip_row,
                    ui_text(
                        "要继续吗？导入时要导入动画封面图吗？",
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        width=content_w,
                        no_wrap=False,
                    ),
                ],
            ),
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
                    power_get,
                    rename_checkbox,
                    force_checkbox,
                    mark_checkbox,
                    ignore_skip_checkbox,
                    with_covers=False,
                ),
            ),
            ft.TextButton(
                content=ui_text("仅封面"),
                # 直接导入封面，是否无视标记由复选框决定。
                on_click=lambda event: _start_from_dialog(
                    owner,
                    dialog,
                    power_get,
                    rename_checkbox,
                    force_checkbox,
                    mark_checkbox,
                    ignore_skip_checkbox,
                    with_covers=True,
                    covers_only=True,
                ),
            ),
            ft.TextButton(
                content=ui_text("我全都要"),
                on_click=lambda event: _start_from_dialog(
                    owner,
                    dialog,
                    power_get,
                    rename_checkbox,
                    force_checkbox,
                    mark_checkbox,
                    ignore_skip_checkbox,
                    with_covers=True,
                ),
            ),
        ],
    )
    page.show_dialog(dialog)


def _start_from_dialog(
    owner: "WatchedPage",
    dialog: ft.AlertDialog,
    power_get,
    rename_checkbox: ft.Checkbox,
    force_checkbox: ft.Checkbox,
    mark_checkbox: ft.Checkbox,
    ignore_skip_checkbox: ft.Checkbox,
    *,
    with_covers: bool,
    covers_only: bool = False,
) -> None:
    power = str(power_get() or "loose")
    rename = bool(rename_checkbox.value)
    force = bool(force_checkbox.value)
    mark_done = bool(mark_checkbox.value)
    # 是否无视「不自动导入」标记，统一取自主弹窗复选框。
    ignore_skip = bool(ignore_skip_checkbox.value)
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


