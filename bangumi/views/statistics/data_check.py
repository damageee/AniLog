"""数据质量检查页。"""

from __future__ import annotations

import flet as ft
from bangumi.ui.events import is_hover
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.data.quarter_core import (
    broadcast_dates,
    quarter_for_month,
)
from bangumi.data.watched_data import (
    Record,
    load_records,
    save_records,
    split_tags,
)
from bangumi.data.statistics.data_check import (
    data_anomalies,
    data_coverage,
    data_missing_items,
)
from bangumi.views.widgets.progress_bar import build_progress_block
from bangumi.ui.constants import (
    HOVER_ROW_OPACITY,
)


YURI_SEASON_NAMES = ("冬天", "春天", "夏天", "秋天")


def yuri_easter_egg(records: list[Record]) -> list[str]:
    marked: set[tuple[int, int]] = set()
    for record in records:
        tags = split_tags(record.get("tag"))
        if "百合" not in tags:
            continue
        for date in broadcast_dates(
            str(record.get("broadcast") or "")
        ):
            year, month = date[0], date[1]
            index, _ = quarter_for_month(month)
            marked.add((year, index))
    if not marked:
        return []
    ordinals = sorted(year * 4 + index for year, index in marked)
    runs: list[tuple[int, int]] = []
    start = ordinal = ordinals[0]
    length = 1
    for value in ordinals[1:]:
        if value == ordinal + 1:
            ordinal = value
            length += 1
            continue
        runs.append((start, length))
        start = ordinal = value
        length = 1
    runs.append((start, length))
    best_start, best_len = runs[0]
    for run_start, run_len in runs:
        if run_len > best_len or (
            run_len == best_len and run_start > best_start
        ):
            best_start, best_len = run_start, run_len
    lines: list[str] = []
    if best_len >= 3:
        first = best_start
        last = best_start + best_len - 1
        start_label = (
            f"{first // 4}年"
            f"{YURI_SEASON_NAMES[first % 4]}"
        )
        end_label = (
            f"{last // 4}年"
            f"{YURI_SEASON_NAMES[last % 4]}"
        )
        lines.append(
            f"你从{start_label}到{end_label}都有百合看，"
            "真是超高校级的幸福啊！"
        )
    marked_ordinals = {
        year * 4 + index for year, index in marked
    }
    full_years = sorted(
        {
            year
            for year, _ in marked
            if all(
                year * 4 + index in marked_ordinals
                for index in range(4)
            )
        }
    )
    if full_years:
        names = ", ".join(str(year) for year in full_years)
        lines.append(
            f"{names}一整年都能有百合看，"
            "真是无比美好的一年啊！"
        )
    return lines


def data_view(page: ft.Page) -> ft.View:
    records = load_records()
    fg = foreground_color(page)
    hover_color = ft.Colors.with_opacity(HOVER_ROW_OPACITY, fg)
    summary_holder = ft.Column(
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[],
    )
    anomaly_holder = ft.Column(
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[],
    )
    egg_holder = ft.Column(
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[],
    )
    missing_holder = ft.Column(
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[],
    )

    def edit_record(record: Record) -> None:
        from bangumi.views.general.entry_form import open_entry_form

        index = next(
            (
                position
                for position, item in enumerate(records)
                if item is record
            ),
            None,
        )

        def on_save(updated: Record) -> None:
            if index is not None and 0 <= index < len(records):
                records[index] = updated
            else:
                for position, item in enumerate(records):
                    if item is record:
                        records[position] = updated
                        break
            save_records(records)
            rebuild()
            try:
                page.update(
                    summary_holder,
                    anomaly_holder,
                    missing_holder,
                    egg_holder,
                )
            except Exception:
                page.update()

        open_entry_form(page, record=record, on_save=on_save)

    def content_width() -> float:
        padding = page_padding()
        horizontal = float(
            (padding.left or 0) + (padding.right or 0)
        )
        return max(
            120.0,
            float(page.width or 1000) - horizontal,
        )

    def fit_rows() -> None:
        width = content_width()
        for control in missing_holder.controls:
            control.width = width

    def missing_row(text: str, record: Record) -> ft.Control:
        row = ft.Container(
            width=content_width(),
            padding=ft.Padding.symmetric(horizontal=6, vertical=9),
            border_radius=6,
            border=ft.Border(
                bottom=ft.BorderSide(
                    1,
                    ft.Colors.with_opacity(0.1, fg),
                )
            ),
            on_click=lambda event, target=record: edit_record(target),
            tooltip="编辑该记录",
            content=ui_text(text, size=14, color=fg),
        )

        def on_hover(event: ft.ControlEvent) -> None:
            hovered = is_hover(event)
            row.bgcolor = hover_color if hovered else None
            row.update()

        row.on_hover = on_hover
        return row

    def rebuild() -> None:
        x, y = data_coverage(records)
        summary_holder.controls = build_progress_block(page, x, y)

        anomaly_controls: list[ft.Control] = []
        for title, lines in data_anomalies(records):
            anomaly_controls.append(
                ui_text(
                    title,
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=fg,
                )
            )
            anomaly_controls.extend(
                ui_text(line, size=14, color=fg)
                for line in lines
            )
        if not anomaly_controls:
            anomaly_controls.append(
                ui_text("暂无异常", size=14, color=fg)
            )
        anomaly_holder.controls = anomaly_controls

        missing_holder.controls = [
            missing_row(text, record)
            for text, record in data_missing_items(records)
        ]
        fit_rows()
        egg_holder.controls = [
            ui_text(
                line,
                size=14,
                color=(
                    ft.Colors.PINK_300
                    if page.theme_mode == ft.ThemeMode.DARK
                    else ft.Colors.PINK_400
                ),
            )
            for line in yuri_easter_egg(records)
        ]

    rebuild()

    body = ft.Column(
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ui_text(
                "覆盖率",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=fg,
            ),
            summary_holder,
            ft.Divider(height=1),
            ui_text(
                "数据质量",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=fg,
            ),
            anomaly_holder,
            egg_holder,
            ft.Divider(height=1),
            ui_text(
                "待补列表",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=fg,
            ),
            missing_holder,
        ],
    )

    view = ft.View(
        route="/statistics/data",
        appbar=ft.AppBar(title=ui_text("数据")),
        padding=page_padding(),
        controls=[vertical_page([body])],
    )
    view.data = {
        "rebuild": lambda: data_view(page)
    }
    previous_resize = page.on_resize

    def on_resize(event: ft.ControlEvent | None = None) -> None:
        if view in page.views:
            fit_rows()
            if page.views[-1] is view:
                try:
                    missing_holder.update()
                except RuntimeError:
                    return
                return
        if (
            previous_resize is not None
            and previous_resize is not on_resize
        ):
            previous_resize(event)

    page.on_resize = on_resize
    return view


