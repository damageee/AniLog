"""设置页的高级设置与字段配置。"""

from __future__ import annotations

import asyncio
import time
from datetime import (
    date,
)
from pathlib import Path

import flet as ft
from bangumi.core.storage import storage_directory
from bangumi.data.preferences import (
    Preferences,
)
from bangumi.data.watched_data import load_records, record_title
from bangumi.services.bgm_pic import (
    COVER_DIRECTORY,
    has_cover,
    save_subject_image,
)
from bangumi.ui.theme import (
    ui_text,
    ui_text_style,
)
from bangumi.ui.interaction import (
    back_icon,
    hover_icon,
)
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.views.navigation import (
    go_back,
    push_view,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.ui.feedback import (
    close_dialog,
    confirmation_dialog,
    show_error_dialog,
)
from bangumi.ui import anim
from bangumi.views.widgets.toast import show_toast


FIXED_COLUMN_LABELS = (
    ("anime", "动画"),
    ("specification", "规格"),
    ("category", "类型"),
    ("tag", "TAG"),
    ("staff", "STAFF"),
    ("studio", "制作公司"),
    ("broadcast", "放送"),
    ("role", "角色"),
    ("rating", "评分"),
)


def _unused_cover_files() -> list[Path]:
    """返回 bgm_cover 目录里 bgm_id 不在已阅记录中的图片。"""
    records = load_records()
    used: set[int] = set()
    for record in records:
        bgm_id = record.get("bgm_id")
        if isinstance(bgm_id, int) and bgm_id != -1:
            used.add(bgm_id)
    root = storage_directory() / COVER_DIRECTORY
    if not root.is_dir():
        return []
    unused: list[Path] = []
    for path in root.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        if not path.stem.isdigit():
            continue
        if int(path.stem) not in used:
            unused.append(path)
    return unused


def open_clean_covers_dialog(page: ft.Page) -> None:
    """确认后清理没有对应已阅记录的封面图。"""
    files = _unused_cover_files()
    if not files:
        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=background_color(page),
                title=ui_text("清理多余封面图"),
                content=ui_text("无可清理图片"),
                title_text_style=ui_text_style(
                    color=foreground_color(page)
                ),
                content_text_style=ui_text_style(
                    color=foreground_color(page)
                ),
                actions=[
                    ft.Button(
                        content=ui_text("确认"),
                        on_click=lambda event: page.pop_dialog(),
                    )
                ],
            )
        )
        return

    def confirm(event: ft.ControlEvent) -> None:
        page.pop_dialog()
        removed = 0
        for path in files:
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        show_toast(page, f"已清理 {removed} 张图片")

    page.show_dialog(
        confirmation_dialog(
            page,
            title="清理多余封面图",
            message=f"是否清理共{len(files)}张无用图片？",
            confirm_label="清理",
            on_confirm=confirm,
        )
    )


def _missing_covers_info() -> tuple[
    int,
    int,
    int,
    int,
    list[tuple[int, str]],
]:
    """统计缺失 bgm_id 与缺失封面，并按 bgm_id 去重待下载列表。"""
    records = load_records()
    total = len(records)
    no_id = 0
    missing = 0
    pending: dict[int, str] = {}
    for record in records:
        bgm_id = record.get("bgm_id")
        if not isinstance(bgm_id, int) or bgm_id == -1:
            no_id += 1
            continue
        if has_cover(bgm_id):
            continue
        missing += 1
        name = record_title(record) or str(bgm_id)
        pending.setdefault(bgm_id, name)
    remaining = total - no_id
    return total, no_id, remaining, missing, list(pending.items())


def _run_missing_cover_download(
    page: ft.Page,
    pending: list[tuple[int, str]],
) -> None:
    """显示进度弹窗并逐一补齐缺失封面。"""
    total = len(pending)
    text_color = foreground_color(page)
    status_text = ui_text("准备中…", size=13)
    counter_text = ui_text(f"0/{total}", size=13)
    progress = ft.ProgressBar(value=0, height=12)
    fail_label = ui_text("0 失败", size=13)
    elapsed_label = ui_text("0s", size=13)
    state: dict[str, object] = {
        "ok": 0,
        "fail": 0,
        "done": 0,
        "abort": False,
        "start": time.monotonic(),
    }

    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=background_color(page),
        title=ui_text("正在补全"),
        content=ft.Column(
            tight=True,
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[status_text, counter_text],
                ),
                progress,
                fail_label,
                elapsed_label,
            ],
        ),
        actions=[],
    )

    def show_result() -> None:
        close_dialog(dialog)
        ok = int(state["ok"])
        fail = int(state["fail"])
        result = ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text("补全完成"),
            content=ui_text(
                f"成功下载 {ok} 个封面，失败 {fail} 个。"
            ),
            title_text_style=ui_text_style(color=text_color),
            content_text_style=ui_text_style(color=text_color),
            actions=[],
        )
        result.actions = [
            ft.Button(
                content=ui_text("确认"),
                on_click=lambda event: close_dialog(result),
            )
        ]
        page.show_dialog(result)

    def abort(event: ft.ControlEvent) -> None:
        # 只设置标志，当前下载结束后停止并进入结果弹窗。
        state["abort"] = True

    dialog.actions = [
        ft.Button(content=ui_text("中止"), on_click=abort)
    ]
    page.show_dialog(dialog)

    async def worker() -> None:
        try:
            for index, (bgm_id, name) in enumerate(
                pending,
                start=1,
            ):
                if state["abort"]:
                    break
                status_text.value = f"正在下载{name}"
                counter_text.value = f"{index - 1}/{total}"
                try:
                    dialog.update()
                except Exception:
                    pass
                result = await asyncio.to_thread(
                    save_subject_image,
                    bgm_id,
                )
                if result is not None:
                    state["ok"] = int(state["ok"]) + 1
                else:
                    state["fail"] = int(state["fail"]) + 1
                state["done"] = index
                progress.value = index / total if total else 0
                counter_text.value = f"{index}/{total}"
                fail_label.value = f"{state['fail']} 失败"
                elapsed_label.value = (
                    f"{int(round(time.monotonic() - float(state['start'])))}s"
                )
                try:
                    dialog.update()
                except Exception:
                    pass
        finally:
            show_result()

    page.run_task(worker)


def open_missing_covers_dialog(page: ft.Page) -> None:
    """检查缺失封面并询问是否补齐。"""
    total, no_id, remaining, missing, pending = (
        _missing_covers_info()
    )
    text_color = foreground_color(page)
    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=background_color(page),
        title=ui_text("检查缺失封面图"),
        content=ft.Column(
            tight=True,
            spacing=4,
            controls=[
                ui_text(
                    f"共{total}部动画，{no_id}部缺失bgm_id",
                    color=text_color,
                ),
                ui_text(
                    (
                        f"剩下的{remaining}部中都有封面，"
                        f"没有缺失。"
                    )
                    if missing == 0
                    else (
                        f"剩下的{remaining}部中有{missing}部"
                        f"缺失封面，是否补齐？"
                    ),
                    color=text_color,
                ),
            ],
        ),
        title_text_style=ui_text_style(color=text_color),
        content_text_style=ui_text_style(color=text_color),
        actions=[],
    )

    def close(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    def start(event: ft.ControlEvent) -> None:
        page.pop_dialog()
        _run_missing_cover_download(page, pending)

    if missing == 0:
        dialog.actions = [
            ft.Button(content=ui_text("确认"), on_click=close)
        ]
    else:
        dialog.actions = [
            ft.Button(content=ui_text("取消"), on_click=close),
            ft.Button(content=ui_text("补齐"), on_click=start),
        ]
    page.show_dialog(dialog)


def _build_advanced_view(page: ft.Page) -> ft.View:
    def back(event: ft.ControlEvent) -> None:
        go_back(page, "/settings/advanced")

    mode_button = ft.Button(
        content=ui_text(anim.MODE_LABELS[anim.animation_mode()], size=18),
        style=ft.ButtonStyle(text_style=ui_text_style(size=18)),
    )

    def cycle_animation(event: ft.ControlEvent) -> None:
        order = ("full", "off")
        current = anim.animation_mode()
        try:
            index = order.index(current)
        except ValueError:
            index = 0
        new_mode = order[(index + 1) % len(order)]
        preferences = Preferences.load()
        preferences.animation_mode = new_mode
        preferences.save()
        anim.set_animation_mode(new_mode)
        mode_button.content = ui_text(anim.MODE_LABELS[new_mode], size=18)
        try:
            mode_button.update()
        except Exception:
            pass

    mode_button.on_click = cycle_animation

    view = ft.View(
        route="/settings/advanced",
        appbar=ft.AppBar(
            title=ui_text("高级设置"),
            automatically_imply_leading=False,
            leading=back_icon(page, "/settings/advanced"),
        ),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.Column(
                        spacing=12,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.STRETCH
                        ),
                        controls=[
                            ft.Button(
                                content=ui_text(
                                    "特殊补完日", size=18
                                ),
                                style=ft.ButtonStyle(
                                    text_style=ui_text_style(size=18)
                                ),
                                on_click=lambda event: (
                                    open_special_dates_dialog(page)
                                ),
                            ),
                            ft.Button(
                                content=ui_text(
                                    "固定表格列", size=18
                                ),
                                style=ft.ButtonStyle(
                                    text_style=ui_text_style(size=18)
                                ),
                                on_click=lambda event: (
                                    open_fixed_columns_dialog(page)
                                ),
                            ),
                            ft.Button(
                                content=ui_text(
                                    "详情页字段显示", size=18
                                ),
                                style=ft.ButtonStyle(
                                    text_style=ui_text_style(size=18)
                                ),
                                on_click=lambda event: (
                                    open_detail_fields_dialog(page)
                                ),
                            ),
                            mode_button,
                            ft.Button(
                                content=ui_text(
                                    "清理多余封面图", size=18
                                ),
                                style=ft.ButtonStyle(
                                    text_style=ui_text_style(size=18)
                                ),
                                on_click=lambda event: (
                                    open_clean_covers_dialog(page)
                                ),
                            ),
                            ft.Button(
                                content=ui_text(
                                    "检查缺失封面图", size=18
                                ),
                                style=ft.ButtonStyle(
                                    text_style=ui_text_style(size=18)
                                ),
                                on_click=lambda event: (
                                    open_missing_covers_dialog(page)
                                ),
                            ),
                        ],
                    )
                ]
            )
        ],
    )
    view.data = {
        "rebuild": lambda: _build_advanced_view(page)
    }
    return view


def open_advanced(page: ft.Page) -> None:
    push_view(page, _build_advanced_view(page))


def open_special_dates_dialog(page: ft.Page) -> None:
    preferences = Preferences.load()
    dates: list[str] = list(
        preferences.special_completion_dates
    ) or [""]
    rows_holder = ft.Column(spacing=6, controls=[])
    border_color = ft.Colors.with_opacity(
        0.35, foreground_color(page)
    )

    def open_date_picker(index: int) -> None:
        try:
            current = date.fromisoformat(dates[index])
        except (ValueError, IndexError):
            current = date.today()
        today = date.today()
        years = [
            str(year)
            for year in range(today.year - 50, today.year + 6)
        ]
        months = [f"{month:02d}" for month in range(1, 13)]
        days = [f"{day:02d}" for day in range(1, 32)]
        year_dropdown = ft.Dropdown(
            value=f"{current.year:04d}",
            options=[
                ft.DropdownOption(key=value, text=value)
                for value in years
            ],
            width=110,
        )
        month_dropdown = ft.Dropdown(
            value=f"{current.month:02d}",
            options=[
                ft.DropdownOption(key=value, text=value)
                for value in months
            ],
            width=90,
        )
        day_dropdown = ft.Dropdown(
            value=f"{current.day:02d}",
            options=[
                ft.DropdownOption(key=value, text=value)
                for value in days
            ],
            width=90,
        )
        picker = ft.AlertDialog(
            modal=True,
            title=ui_text("选择日期"),
            content=ft.Row(
                spacing=8,
                controls=[
                    year_dropdown,
                    month_dropdown,
                    day_dropdown,
                ],
            ),
            actions=[],
        )

        def cancel_pick(event: ft.ControlEvent) -> None:
            page.pop_dialog()

        def confirm_pick(event: ft.ControlEvent) -> None:
            page.pop_dialog()
            try:
                selected = date(
                    int(year_dropdown.value or current.year),
                    int(month_dropdown.value or current.month),
                    int(day_dropdown.value or current.day),
                )
            except (TypeError, ValueError):
                show_error_dialog(
                    page,
                    title="日期无效",
                    message="请选择有效的日期",
                )
                return
            dates[index] = selected.isoformat()
            render_rows()

        picker.actions = [
            ft.TextButton(
                content=ui_text("取消"),
                on_click=cancel_pick,
            ),
            ft.Button(
                content=ui_text("确定"),
                on_click=confirm_pick,
            ),
        ]
        page.show_dialog(picker)

    def delete_date(index: int) -> None:
        if len(dates) <= 1:
            dates[index] = ""
            render_rows()
            return
        del dates[index]
        render_rows()

    def add_date(event: ft.ControlEvent) -> None:
        dates.append("")
        render_rows()

    def date_row(index: int, value: str) -> ft.Row:
        button = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(
                horizontal=10,
                vertical=8,
            ),
            border_radius=6,
            border=ft.Border.all(1, border_color),
            on_click=lambda event, i=index: open_date_picker(i),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CALENDAR_MONTH, size=18),
                    ui_text(value or "选择日期", size=14),
                ],
            ),
        )
        trailing: list[ft.Control] = [
            hover_icon(
                page,
                ft.Icons.DELETE_OUTLINE,
                tooltip="删除",
                on_click=lambda event, i=index: delete_date(i),
            )
        ]
        if index == len(dates) - 1:
            trailing.append(
                hover_icon(
                    page,
                    ft.Icons.ADD,
                    tooltip="新增",
                    on_click=add_date,
                )
            )
        return ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[button, *trailing],
        )

    def render_rows() -> None:
        rows_holder.controls = [
            date_row(index, value)
            for index, value in enumerate(dates)
        ]
        try:
            rows_holder.update()
        except Exception:
            pass

    render_rows()
    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("特殊补完日"),
        content=ft.Column(
            tight=True,
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ui_text(
                    "在部分和「补完」相关的统计（如单日最高补完数）时，"
                    "以下设定的日期将不参与统计",
                    size=13,
                ),
                rows_holder,
            ],
        ),
        actions=[],
    )

    def cancel(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    def confirm(event: ft.ControlEvent) -> None:
        page.pop_dialog()
        preferences.special_completion_dates = [
            value for value in dates if value
        ]
        preferences.save()

    dialog.actions = [
        ft.TextButton(content=ui_text("取消"), on_click=cancel),
        ft.Button(content=ui_text("确认"), on_click=confirm),
    ]
    page.show_dialog(dialog)


def open_fixed_columns_dialog(page: ft.Page) -> None:
    preferences = Preferences.load()
    fixed = set(preferences.fixed_columns)
    clear_checkbox = ft.Checkbox(
        label=ui_text(
            "编辑条目时输入Bangumi ID后仍然清空忽略的字段"
        ),
        value=preferences.clear_fixed_fields_on_id_import,
    )
    checkboxes: list[tuple[str, ft.Checkbox]] = [
        (
            key,
            ft.Checkbox(
                label=ui_text(f"{label}({key})"),
                value=key in fixed,
            ),
        )
        for key, label in FIXED_COLUMN_LABELS
    ]
    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("固定表格列"),
        content=ft.Column(
            tight=True,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ui_text(
                    "以下勾选的字段名，所对应的列在追加/编辑条目、"
                    "填充表格时发生的从 Bangumi 自动导入中一律忽略"
                    "（不论原字段是否为空）。",
                    size=13,
                ),
                clear_checkbox,
                *[checkbox for _, checkbox in checkboxes],
            ],
        ),
        actions=[],
    )

    def cancel(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    def confirm(event: ft.ControlEvent) -> None:
        page.pop_dialog()
        preferences.fixed_columns = [
            key
            for key, checkbox in checkboxes
            if checkbox.value
        ]
        preferences.clear_fixed_fields_on_id_import = bool(
            clear_checkbox.value
        )
        preferences.save()

    dialog.actions = [
        ft.TextButton(content=ui_text("取消"), on_click=cancel),
        ft.Button(content=ui_text("确认"), on_click=confirm),
    ]
    page.show_dialog(dialog)


def open_detail_fields_dialog(page: ft.Page) -> None:
    preferences = Preferences.load()
    checks: list[tuple[str, ft.Checkbox]] = [
        (
            "detail_show_rating",
            ft.Checkbox(
                label=ui_text("评分(detail_show_rating)"),
                value=preferences.detail_show_rating,
            ),
        ),
        (
            "detail_show_completion",
            ft.Checkbox(
                label=ui_text("补完(detail_show_completion)"),
                value=preferences.detail_show_completion,
            ),
        ),
        (
            "detail_show_remark",
            ft.Checkbox(
                label=ui_text("备注(detail_show_remark)"),
                value=preferences.detail_show_remark,
            ),
        ),
    ]
    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("详情页字段显示"),
        content=ft.Column(
            tight=True,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ui_text(
                    "在具体的动画详情页，是否显示以下字段的值：",
                    size=13,
                ),
                *[checkbox for _, checkbox in checks],
            ],
        ),
        actions=[],
    )

    def cancel(event: ft.ControlEvent) -> None:
        page.pop_dialog()

    def confirm(event: ft.ControlEvent) -> None:
        page.pop_dialog()
        values = {
            key: bool(checkbox.value)
            for key, checkbox in checks
        }
        preferences.detail_show_rating = values[
            "detail_show_rating"
        ]
        preferences.detail_show_completion = values[
            "detail_show_completion"
        ]
        preferences.detail_show_remark = values[
            "detail_show_remark"
        ]
        preferences.save()

    dialog.actions = [
        ft.TextButton(content=ui_text("取消"), on_click=cancel),
        ft.Button(content=ui_text("确认"), on_click=confirm),
    ]
    page.show_dialog(dialog)


