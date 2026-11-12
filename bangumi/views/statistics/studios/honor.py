"""制作公司荣誉榜页。"""

from __future__ import annotations

from urllib.parse import (
    quote,
)
import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.views.general.bar_chart import (
    build_bar_chart_view,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.feedback import (
    no_records_note,
)
from bangumi.views.navigation import (
    push_view,
)
from bangumi.ui.layout import (
    vertical_page,
)
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.views.navigation import (
    ENTRY,
)
from bangumi.views.navigation import (
    open_detail,
)
from bangumi.data.watched_data import (
    Record,
    load_records,
    record_title,
)
from bangumi.data.statistics.constants import (
    HONOR_COLUMNS,
    HONOR_TOTAL,
)
from bangumi.data.statistics.studios_honor import (
    _company_color,
    _honor_group,
    _honor_metrics,
    _honor_rating,
    _honor_studios,
    _honor_year,
)
from bangumi.views.statistics.common.shared import (
    _back_view,
)
from .homepage import open_studio_page
from bangumi.ui.constants import (
    ANIM_BASE_MS,
    HOVER_SCALE_HONOR,
)


def _honor_cell(
    page: ft.Page,
    column: str,
    label: str,
    group_records: list[Record],
    records: list[Record],
    meta: dict,
    fg: str,
    secondary: str,
    dark: bool,
    data_w: float,
    cell_h: float,
    works_records: list[Record] | None = None,
    works_label: str | None = None,
) -> ft.Container:
    if meta.get("empty"):
        return ft.Container(
            width=data_w,
            height=cell_h,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.with_opacity(0.14, fg),
            on_click=None,
            content=ui_text(
                "—",
                size=13,
                color=secondary,
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        )

    studio = str(meta["display"])
    value = meta["value"]
    text = f"{studio}({value})"
    if len(meta["primary_tied"]) >= 2:
        text += "..."

    arr = meta["arr"]
    decimals = meta["decimals"]
    remark = meta["remark"]
    chart_title = f"{column}（{label}）"

    def _works_sample() -> list[Record]:
        return (
            works_records
            if works_records is not None
            else group_records
        )

    def build_works_view(
        chart_records: list[Record],
        studio_name: str,
    ) -> ft.View:
        works_by_name: dict[str, Record] = {}
        works: list[tuple[str, int]] = []
        for record in chart_records:
            if studio_name not in _honor_studios(record):
                continue
            anime_name = record_title(record)
            if not anime_name:
                continue
            works.append(
                (anime_name, _honor_rating(record) or 0)
            )
            works_by_name.setdefault(anime_name, record)
        works_title = (
            f"{studio_name}（{works_label or label}）"
        )
        sample_names = {
            record_title(record)
            for record in chart_records
        }

        def on_work_click(name: str) -> None:
            record = works_by_name.get(name)
            if record is None:
                return
            open_detail(page, chart_records, record, ENTRY)

        def rebuild_works() -> ft.View:
            fresh = [
                record
                for record in load_records()
                if record_title(record)
                in sample_names
            ]
            return build_works_view(fresh, studio_name)

        return build_bar_chart_view(
            page,
            works,
            max_value=100,
            reverse=False,
            title=works_title,
            route=(
                "/statistics/studio-works/"
                + quote(works_title, safe="")
            ),
            decimals=0,
            on_bar_click=on_work_click,
            rebuild=rebuild_works,
        )

    def on_bar_click(studio_name: str) -> None:
        push_view(page, build_works_view(_works_sample(), studio_name))

    def on_company_long_press(studio_name: str) -> None:
        open_studio_page(page, records, studio_name)

    def _honor_scope(fresh: list[Record]) -> list[Record]:
        if label == HONOR_TOTAL:
            return fresh
        try:
            year = int(label)
        except ValueError:
            return fresh
        if column == "整体发挥":
            years = (year - 2, year - 1, year)
            return [
                record
                for record in fresh
                if _honor_year(record) in years
            ]
        return [
            record
            for record in fresh
            if _honor_year(record) == year
        ]

    def build_honor_chart(
        chart_arr,
        chart_decimals: int,
        chart_remark: str,
        chart_records: list[Record],
    ) -> ft.View:
        def click(studio_name: str) -> None:
            push_view(
                page, build_works_view(chart_records, studio_name)
            )

        def rebuild_honor_chart() -> ft.View:
            fresh = load_records()
            fresh_scope = _honor_scope(fresh)
            fresh_meta = _honor_metrics(
                column,
                label,
                _honor_group(fresh_scope),
            )
            return build_honor_chart(
                fresh_meta.get("arr", chart_arr),
                fresh_meta.get("decimals", chart_decimals),
                fresh_meta.get("remark", chart_remark),
                fresh_scope,
            )

        max_value = (
            100
            if column in ("整体发挥", "最高力作")
            else None
        )
        return build_bar_chart_view(
            page,
            chart_arr,
            max_value=max_value,
            reverse=False,
            title=chart_title,
            route=(
                "/statistics/honor/"
                + quote(chart_title, safe="")
            ),
            decimals=chart_decimals,
            on_bar_click=click,
            on_bar_long_press=on_company_long_press,
            remark=chart_remark,
            rebuild=rebuild_honor_chart,
        )

    def open_chart(event: ft.ControlEvent) -> None:
        push_view(
            page,
            build_honor_chart(
                arr,
                decimals,
                remark,
                _honor_scope(records),
            ),
        )

    cell = ft.Container(
        width=data_w,
        height=cell_h,
        border_radius=6,
        alignment=ft.Alignment.CENTER,
        bgcolor=_company_color(studio, dark),
        on_click=open_chart,
        content=ui_text(
            text,
            size=13,
            color=fg,
            no_wrap=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    )
    cell.animate_scale = animation(
        ANIM_BASE_MS, ft.AnimationCurve.EASE_OUT
    )
    cell.scale = 1.0

    def _on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        cell.scale = HOVER_SCALE_HONOR if hovered else 1.0
        try:
            cell.update()
        except Exception:
            pass

    cell.on_hover = _on_hover
    return cell


def honor_view(page: ft.Page) -> ft.View:
    records = load_records()
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.55, fg)
    dark = page.theme_mode == ft.ThemeMode.DARK

    if not records:
        return _back_view(
            page,
            route="/statistics/studios/honor",
            title="制作公司 —— 荣誉榜",
            rebuild=lambda: honor_view(page),
            controls=[
                vertical_page(
                    [
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                no_records_note(
                                    page,
                                    height=60,
                                    width=max(
                                        200.0,
                                        float(page.width or 1000) - 48,
                                    ),
                                )
                            ],
                        )
                    ]
                )
            ],
        )

    available = fit_chart_width(page, 1000.0, min_width=240.0)
    label_w = min(88.0, max(56.0, available * 0.18))
    data_w = max(80.0, (available - label_w - 4 * 3) / 3)
    cell_h = 52
    header_bg = ft.Colors.with_opacity(0.10, fg)
    label_bg = ft.Colors.with_opacity(0.05, fg)

    def text_cell(
        text: str,
        width: float,
        bgcolor: str,
    ) -> ft.Container:
        return ft.Container(
            width=width,
            height=cell_h,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
            bgcolor=bgcolor,
            on_click=None,
            content=ui_text(
                text,
                size=13,
                color=fg,
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        )

    corner_cell = text_cell("", label_w, header_bg)
    header_cells: list[ft.Container] = [
        text_cell(name, data_w, header_bg)
        for name in HONOR_COLUMNS
    ]
    years = sorted(
        {
            _honor_year(record)
            for record in records
            if _honor_year(record) is not None
        }
    )
    rows: list[tuple[str, list[Record]]] = []
    for year in years:
        year_records = [
            record
            for record in records
            if _honor_year(record) == year
        ]
        if not any(
            _honor_rating(record) is not None
            for record in year_records
        ):
            continue
        rows.append((str(year), year_records))
    rows.append((HONOR_TOTAL, records))

    grid_rows: list[ft.Control] = [
        ft.Row(
            spacing=4,
            controls=[corner_cell, *header_cells],
        )
    ]
    label_cells: list[ft.Container] = []
    data_cells: list[ft.Container] = []

    def set_honor_scale(
        target: ft.Container,
        on: bool,
    ) -> None:
        if target.animate_scale is None:
            target.animate_scale = animation(
                ANIM_BASE_MS,
                ft.AnimationCurve.EASE_OUT,
            )
        target.scale = HOVER_SCALE_HONOR if on else 1.0
        try:
            target.update()
        except Exception:
            pass

    row_data: list[
        tuple[str, list[Record], list[Record], list[dict]]
    ] = []
    for label, group_records in rows:
        groups = _honor_group(group_records)
        if label == HONOR_TOTAL:
            avg_groups = groups
            avg_records = records
        else:
            try:
                year = int(label)
            except ValueError:
                year = None
            if year is None:
                avg_groups = groups
                avg_records = group_records
            else:
                sample = [
                    record
                    for record in records
                    if _honor_year(record)
                    in (year - 2, year - 1, year)
                ]
                avg_groups = _honor_group(sample)
                avg_records = sample
        metas = [
            _honor_metrics(
                column,
                label,
                (
                    avg_groups
                    if column == "整体发挥"
                    else groups
                ),
            )
            for column in HONOR_COLUMNS
        ]
        row_data.append((label, group_records, avg_records, metas))

    counter: dict[str, int] = {}
    for _, _, _, metas in row_data:
        for meta in metas:
            if meta.get("empty"):
                continue
            tied = meta["primary_tied"]
            if len(tied) >= 2:
                for company in tied:
                    counter[company] = counter.get(company, 0) + 1
            else:
                original = meta["original"]
                counter[original] = counter.get(original, 0) + 1

    for _, _, _, metas in row_data:
        for meta in metas:
            if meta.get("empty"):
                meta["display"] = ""
                continue
            tied = meta["primary_tied"]
            if len(tied) >= 2:
                best_count = max(
                    counter[company] for company in tied
                )
                winners = [
                    company
                    for company in tied
                    if counter[company] == best_count
                ]
                if len(winners) == 1:
                    meta["display"] = winners[0]
                else:
                    meta["display"] = meta["original"]
            else:
                meta["display"] = meta["original"]

    for label, group_records, avg_records, metas in row_data:
        label_cell = text_cell(label, label_w, label_bg)
        label_cells.append(label_cell)
        row_cells: list[ft.Control] = [label_cell]
        for column, meta in zip(HONOR_COLUMNS, metas):
            if column == "整体发挥":
                cell_works = avg_records
                if label == HONOR_TOTAL:
                    cell_label = label
                else:
                    cell_label = f"{int(label) - 2}-{label}"
            else:
                cell_works = group_records
                cell_label = label
            cell = _honor_cell(
                page,
                column,
                label,
                group_records,
                records,
                meta,
                fg,
                secondary,
                dark,
                data_w,
                cell_h,
                works_records=cell_works,
                works_label=cell_label,
            )
            data_cells.append(cell)
            row_cells.append(
                ft.GestureDetector(
                    on_long_press_start=(
                        lambda event, c=cell: set_honor_scale(c, True)
                    ),
                    on_long_press_end=(
                        lambda event, c=cell: set_honor_scale(c, False)
                    ),
                    on_long_press_cancel=(
                        lambda event, c=cell: set_honor_scale(c, False)
                    ),
                    content=cell,
                )
            )
        grid_rows.append(
            ft.Row(spacing=4, controls=row_cells)
        )
    grid = ft.Column(
        spacing=4,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=grid_rows,
    )
    board = ft.Row(
        width=available,
        scroll=ft.Scrollbar(
            orientation=ft.ScrollbarOrientation.BOTTOM,
            thumb_visibility=True,
            track_visibility=True,
        ),
        controls=[grid],
    )
    note = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ui_text(
                "整体发挥为近3年整体发挥",
                size=12,
                color=ft.Colors.with_opacity(0.55, fg),
            )
        ],
    )
    current_data = {"value": data_w, "label": label_w}

    view = _back_view(
        page,
        route="/statistics/studios/honor",
        title="制作公司 —— 荣誉榜",
        controls=[vertical_page([board, note])],
        rebuild=lambda: honor_view(page),
    )

    previous_resize = page.on_resize

    def on_resize(event: ft.ControlEvent) -> None:
        if view in page.views and page.views[-1] is view:
            width = fit_chart_width(page, 1000.0, min_width=240.0)
            new_label = min(88.0, max(56.0, width * 0.18))
            new_data = max(80.0, (width - new_label - 12) / 3)
            changed = False
            if (
                abs(new_data - current_data["value"]) > 1
                or abs(new_label - current_data["label"]) > 1
            ):
                current_data["value"] = new_data
                current_data["label"] = new_label
                for cell in [*header_cells, *data_cells]:
                    cell.width = new_data
                corner_cell.width = new_label
                for cell in label_cells:
                    cell.width = new_label
                changed = True
            if abs(float(board.width or 0) - width) > 1:
                board.width = width
                changed = True
            if changed:
                try:
                    grid.update()
                    board.update()
                except Exception:
                    pass
        if previous_resize is not None:
            previous_resize(event)

    page.on_resize = on_resize
    return view


