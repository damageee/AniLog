"""已阅页面 mixin：table。"""

from __future__ import annotations

import math

import flet as ft

from bangumi.ui.text_metrics import text_width, truncate_display
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import (
    SIMSUN_FONT,
    stats_text,
    stats_text_style,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.views.navigation import (
    CATEGORY,
    ENTRY,
    ROLE,
    REMARK,
)
from bangumi.views.widgets.links import (
    AuthorLink,
    BroadcastLink,
    DetailLink,
    StudioLink,
    TagChips,
    highlight_spans,
)
from bangumi.views.general.detail_role import first_role_name
from bangumi.views.watched.header import (
    FLOATING_LABEL_SIZE,
    HEADER_HEIGHT,
    DraggableHeader,
)
from bangumi.data.watched_data import (
    WATCHED_COLUMNS,
    Record,
    split_tags,
)

from bangumi.views.watched.constants import *

class TableMixin:
    def _table_scroll_area(self) -> ft.Row:
        self._refresh_table_data()
        scroll = getattr(self, "_table_scroll_row", None)
        if scroll is None:
            self.table_body = ft.Column(
                width=self._last_table_width,
                spacing=0,
                controls=[self._table_body_table],
            )
            scroll = ft.Row(
                scroll=ft.Scrollbar(
                    orientation=ft.ScrollbarOrientation.TOP,
                    thumb_visibility=True,
                    track_visibility=True,
                    interactive=True,
                ),
                on_scroll=self._record_horizontal_offset,
                scroll_interval=100,
                controls=[
                    ft.Column(
                        tight=True,
                        spacing=0,
                        controls=[
                            ft.Container(height=14),
                            self._table_header_table,
                            self.table_body,
                        ],
                    )
                ],
            )
            self._table_scroll_row = scroll
        else:
            self.table_body = scroll.controls[0].controls[2]
        inner = scroll.controls[0]
        if inner.controls[1] is not self._table_header_table:
            inner.controls[1] = self._table_header_table
        if inner.controls[2] is not self.table_body:
            inner.controls[2] = self.table_body
        self.table_body.controls = [self._table_body_table]
        self.table_scroll = scroll
        self.table_body.width = self._last_table_width
        return scroll

    def _table_body_height(self) -> float:
        page_height = float(self.page.height or 800)
        view = self.page.views[-1] if self.page.views else None
        appbar = getattr(view, "appbar", None)
        appbar_h = float(
            getattr(appbar, "toolbar_height", None) or 56.0
        )
        compact = is_compact_layout(self.page)
        extra_filters = len(self.filters) * 40.0
        reserve = 500.0 if not compact else 620.0
        reserve += extra_filters
        return max(
            MIN_TABLE_BODY_HEIGHT,
            page_height - appbar_h - reserve,
        )

    def _record_horizontal_offset(self, event: ft.OnScrollEvent) -> None:
        if self._restoring_scroll:
            return
        self.state.horizontal_offset = max(0.0, float(event.pixels))

    def _record_vertical_offset(self, event: ft.OnScrollEvent) -> None:
        if self._restoring_scroll:
            return
        self.state.vertical_offset = max(0.0, float(event.pixels))

    def _refresh_table_data(self) -> None:
        display_records = self._display_records()
        start = self.current_page * self.page_size
        page_records = display_records[
            start : start + self.page_size
        ]
        merge = self.preferences.merge_same_anime
        group_numbers: list[int] = []
        group_starts: list[bool] = []
        if merge:
            previous_key: str | None = None
            group_no = 0
            limit = start + self.page_size
            for record in display_records[:limit]:
                current_key = self._merge_key(record)
                if group_no == 0 or current_key != previous_key:
                    group_no += 1
                    group_starts.append(True)
                else:
                    group_starts.append(False)
                group_numbers.append(group_no)
                previous_key = current_key
        ordered_columns = self._visible_column_labels()
        widths = {
            key: self._column_width(key, label, page_records, start)
            for key, label in ordered_columns
        }
        visible_keys = [key for key, _ in ordered_columns]
        self._last_visible_keys = visible_keys
        self._last_widths = widths
        table_width = (
            sum(widths[key] for key in visible_keys)
            + TABLE_HORIZONTAL_MARGIN * 2
            + TABLE_COLUMN_SPACING * max(0, len(visible_keys) - 1)
        )
        self._last_table_width = table_width
        self._last_row_heights = [DATA_ROW_HEIGHT] * len(page_records)

        theme_mode = self.page.theme_mode
        records_version = getattr(self, "_records_version", 0)
        width_values = tuple(widths[key] for key in visible_keys)
        layout_sig = hash(
            (
                tuple(visible_keys),
                width_values,
                table_width,
                theme_mode,
            )
        )
        header_sig = hash(
            (
                tuple(visible_keys),
                width_values,
                self.sort_column,
                self.sort_ascending,
                self.preferences.merge_same_anime,
                theme_mode,
            )
        )
        rows_sig = hash(
            (
                tuple(visible_keys),
                width_values,
                start,
                tuple(
                    tuple(
                        str(record.get(k, ""))
                        for k in visible_keys
                    )
                    for record in page_records
                ),
                (
                    tuple(group_numbers[start : start + len(page_records)])
                    if merge
                    else ()
                ),
                (
                    tuple(group_starts[start : start + len(page_records)])
                    if merge
                    else ()
                ),
                self.search_query,
                self.search_current,
                self.preferences.merge_same_anime,
                self.preferences.highlight_public_sequels,
                theme_mode,
                records_version,
                hash(
                    tuple(
                        (str(record.get("tag", "")),)
                        for record in self.records
                    )
                ),
            )
        )

        header_table = getattr(self, "_table_header_table", None)
        if header_table is None or getattr(
            self, "_table_header_sig", None
        ) != header_sig:
            header_table = ft.DataTable(
                columns=[
                    self._build_column(key, label, widths[key])
                    for key, label in ordered_columns
                ],
                rows=[],
                width=table_width,
                column_spacing=TABLE_COLUMN_SPACING,
                horizontal_margin=TABLE_HORIZONTAL_MARGIN,
                heading_row_height=48,
                show_bottom_border=True,
                sort_column_index=None,
                sort_ascending=self.sort_ascending,
                data_text_style=stats_text_style(),
                heading_text_style=stats_text_style(
                    weight=ft.FontWeight.BOLD,
                ),
            )
            self._table_header_table = header_table
            self._table_header_sig = header_sig

        body_table = getattr(self, "_table_body_table", None)
        if body_table is None:
            body_table = ft.DataTable(
                columns=[],
                rows=[],
                width=table_width,
                column_spacing=TABLE_COLUMN_SPACING,
                horizontal_margin=TABLE_HORIZONTAL_MARGIN,
                data_row_min_height=DATA_ROW_HEIGHT,
                data_row_max_height=float("inf"),
                heading_row_height=0,
                show_bottom_border=True,
                sort_column_index=None,
                sort_ascending=self.sort_ascending,
                data_text_style=stats_text_style(),
                heading_text_style=stats_text_style(
                    weight=ft.FontWeight.BOLD,
                ),
            )
            self._table_body_table = body_table
            self._table_layout_sig = None
            self._table_rows_sig = None
            self._table_row_cache = {}

        if getattr(self, "_table_layout_sig", None) != layout_sig:
            body_table.columns = [
                ft.DataColumn(
                    label=ft.Container(
                        width=widths[key],
                        height=1,
                    ),
                )
                for key in visible_keys
            ]
            header_table.width = table_width
            body_table.width = table_width
            self._table_layout_sig = layout_sig

        if getattr(self, "_table_rows_sig", None) != rows_sig:
            cache: dict[tuple, tuple[int, ft.DataRow]] = getattr(
                self, "_table_row_cache", {}
            )
            new_cache: dict[tuple, tuple[int, ft.DataRow]] = {}
            rows: list[ft.DataRow] = []
            for offset, record in enumerate(page_records):
                absolute = start + offset
                if merge:
                    is_group_start = group_starts[absolute]
                    display_number = (
                        group_numbers[absolute]
                        if is_group_start
                        else None
                    )
                else:
                    is_group_start = True
                    display_number = absolute + 1
                row_key = (
                    absolute,
                    display_number,
                    is_group_start,
                )
                row_sig = hash(
                    (
                        tuple(visible_keys),
                        tuple(
                            str(record.get(k, ""))
                            for k in visible_keys
                        ),
                        display_number,
                        is_group_start,
                        width_values,
                        self.search_query,
                        self.search_current,
                        theme_mode,
                        records_version,
                    )
                )
                cached = cache.get(row_key)
                if cached is not None and cached[0] == row_sig:
                    row = cached[1]
                else:
                    row = self._build_row(
                        absolute + 1,
                        record,
                        ordered_columns,
                        widths,
                        self.records,
                        display_number=display_number,
                        is_group_start=is_group_start,
                    )
                rows.append(row)
                new_cache[row_key] = (row_sig, row)
            body_table.rows = rows
            self._table_row_cache = new_cache
            self._table_rows_sig = rows_sig

    def _build_column(
        self,
        key: str,
        label: str,
        width: int,
    ) -> ft.DataColumn:
        if key in ("number", "entry"):
            label_control: ft.Control = stats_text(
                label,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        else:
            label_control = DraggableHeader(
                self.page,
                key=key,
                label=label,
                width=width,
                floating_width=max(
                    60,
                    text_width(
                        label,
                        bold=True,
                        size=FLOATING_LABEL_SIZE,
                    )
                    + 16,
                ),
                anchor_positions=self.anchor_positions,
                move_column=self.move_column,
            ).control()

        sortable = (
            key not in ("number", "entry")
            and not self.preferences.merge_same_anime
        )
        arrow_size = 18
        arrow_gap = 3
        label_px = text_width(label, bold=True)
        text_left = (width - label_px) / 2
        text_right = (width + label_px) / 2
        shift = 0.0
        if sortable and self.sort_column == key:
            need = (
                text_right
                + arrow_gap
                + arrow_size
                - (width - 2)
            )
            if need > 0:
                # 只左移刚好够用的距离，保证文字不会被推出左边界
                shift = min(need, max(text_left, 0.0))

        stack_controls: list[ft.Control] = [
            ft.Container(
                left=-shift,
                top=0,
                width=width,
                height=HEADER_HEIGHT,
                alignment=ft.Alignment.CENTER,
                content=label_control,
            )
        ]
        if sortable and self.sort_column == key:
            arrow_left = min(
                max(text_right - shift + arrow_gap, 0.0),
                max(width - arrow_size - 2, 0.0),
            )
            stack_controls.append(
                ft.Container(
                    left=arrow_left,
                    top=(HEADER_HEIGHT - arrow_size) / 2,
                    width=arrow_size,
                    height=arrow_size,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(
                        icon=(
                            ft.Icons.ARROW_UPWARD
                            if self.sort_ascending
                            else ft.Icons.ARROW_DOWNWARD
                        ),
                        size=14,
                        color=foreground_color(self.page),
                    ),
                    on_click=(
                        lambda event, column=key: self._sort_by(column)
                    ),
                )
            )

        return ft.DataColumn(
            label=ft.Container(
                content=ft.Stack(
                    width=width,
                    height=HEADER_HEIGHT,
                    controls=stack_controls,
                ),
                width=width,
                height=HEADER_HEIGHT,
                alignment=ft.Alignment.CENTER,
                on_click=(
                    (lambda event, column=key: self._sort_by(column))
                    if sortable
                    else None
                ),
            ),
        )

    def _build_row(
        self,
        index: int,
        record: Record,
        ordered_columns: list[tuple[str, str]],
        widths: dict[str, int],
        records: list[Record],
        *,
        display_number: int | None = None,
        is_group_start: bool = True,
    ) -> ft.DataRow:
        cells: list[ft.DataCell] = []
        record_index = index - 1
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        for key, _ in ordered_columns:
            highlighted = (
                key == "number"
                and self.preferences.highlight_public_sequels
                and record.get("sequel") is True
            )
            if key == "number":
                value = (
                    str(display_number)
                    if display_number is not None
                    else ""
                )
            elif key == "entry":
                value = str(
                    record.get("entry") or record.get("anime") or ""
                )
            else:
                value = str(record.get(key, ""))
            display = value.replace("\n", " ")

            active_start: int | None = None
            active_end: int | None = None
            if (
                self.search_query
                and 0 <= self.search_current < len(self.search_results)
            ):
                current = self.search_results[self.search_current]
                if current[0] == record_index and current[1] == key:
                    active_start = current[2]
                    active_end = current[3]

            if key == "entry":
                content = (
                    DetailLink(
                        self.page,
                        records,
                        record,
                        ENTRY,
                        font_family=SIMSUN_FONT,
                        text=display,
                        no_wrap=True,
                        reload_records=False,
                    )
                    if is_group_start and display.strip()
                    else stats_text("", no_wrap=True)
                )
            elif key == "anime":
                content: ft.Control = DetailLink(
                    self.page,
                    records,
                    record,
                    ENTRY,
                    text=display,
                    no_wrap=True,
                    font_family=SIMSUN_FONT,
                    highlight_query=self.search_query,
                    highlight_start=active_start,
                    highlight_end=active_end,
                    reload_records=False,
                )
            elif key == "category":
                content = DetailLink(
                    self.page,
                    records,
                    record,
                    CATEGORY,
                    text=display,
                    no_wrap=True,
                    font_family=SIMSUN_FONT,
                    highlight_query=self.search_query,
                    highlight_start=active_start,
                    highlight_end=active_end,
                )
            elif key == "author":
                content = AuthorLink(
                    self.page,
                    records,
                    record,
                    text=display,
                    no_wrap=True,
                    font_family=SIMSUN_FONT,
                    highlight_query=self.search_query,
                    highlight_start=active_start,
                    highlight_end=active_end,
                )
            elif key == "studio":
                content = StudioLink(
                    self.page,
                    records,
                    record,
                    text=display,
                    no_wrap=True,
                    font_family=SIMSUN_FONT,
                    highlight_query=self.search_query,
                    highlight_start=active_start,
                    highlight_end=active_end,
                )
            elif key == "broadcast":
                content = BroadcastLink(
                    self.page,
                    records,
                    record,
                    text=display,
                    no_wrap=True,
                    font_family=SIMSUN_FONT,
                    highlight_query=self.search_query,
                    highlight_start=active_start,
                    highlight_end=active_end,
                )
            elif key == "role":
                name = first_role_name(display)
                content = (
                    DetailLink(
                        self.page,
                        records,
                        record,
                        ROLE,
                        text=name,
                        no_wrap=True,
                        font_family=SIMSUN_FONT,
                        highlight_query=self.search_query,
                        highlight_start=active_start,
                        highlight_end=active_end,
                    )
                    if name
                    else stats_text("", no_wrap=True)
                )
            elif key == "remark":
                full = str(record.get("remark", "") or "")
                content = (
                    DetailLink(
                        self.page,
                        records,
                        record,
                        REMARK,
                        text=truncate_display(full, 100),
                        no_wrap=True,
                        font_family=SIMSUN_FONT,
                        highlight_query=self.search_query,
                        highlight_start=active_start,
                        highlight_end=active_end,
                    )
                    if full.strip()
                    else stats_text("", no_wrap=True)
                )
            elif key == "tag":
                active_tag = None
                if self.search_query and active_start is not None:
                    active_tag = self._tag_at_offset(
                        record,
                        active_start,
                    )
                content = TagChips(
                    self.page,
                    records,
                    record,
                    self.preferences.tag_colors,
                    font_family=SIMSUN_FONT,
                    highlight_query=self.search_query,
                    active_tag=active_tag,
                    wrap=False,
                )
            elif key == "number":
                content = stats_text(
                    display,
                    color=(
                        ft.Colors.RED
                        if highlighted
                        else None
                    ),
                    text_align=ft.TextAlign.CENTER,
                    no_wrap=True,
                )
            elif key == "completion":
                month_key = self._completion_month(display)
                if self.search_query and display:
                    base_text: ft.Control = stats_text(
                        "",
                        spans=highlight_spans(
                            display,
                            self.search_query,
                            dark=dark,
                            active_start=active_start,
                            active_end=active_end,
                        ),
                        color=(
                            ft.Colors.RED
                            if highlighted
                            else None
                        ),
                        text_align=ft.TextAlign.CENTER,
                        no_wrap=True,
                    )
                else:
                    base_text = stats_text(
                        display,
                        color=(
                            ft.Colors.RED
                            if highlighted
                            else None
                        ),
                        text_align=ft.TextAlign.CENTER,
                        no_wrap=True,
                    )
                content = (
                    ft.Container(
                        on_click=(
                            lambda event, mk=month_key: (
                                self._open_completion_month(mk)
                            )
                        ),
                        content=base_text,
                    )
                    if month_key is not None and display.strip()
                    else base_text
                )
            else:
                if self.search_query and display:
                    content = stats_text(
                        "",
                        spans=highlight_spans(
                            display,
                            self.search_query,
                            dark=dark,
                            active_start=active_start,
                            active_end=active_end,
                        ),
                        color=(
                            ft.Colors.RED
                            if highlighted
                            else None
                        ),
                        text_align=ft.TextAlign.CENTER,
                        no_wrap=True,
                    )
                else:
                    content = stats_text(
                        display,
                        color=(
                            ft.Colors.RED
                            if highlighted
                            else None
                        ),
                        text_align=ft.TextAlign.CENTER,
                        no_wrap=True,
                    )

            if isinstance(content, ft.Text):
                content.width = widths[key]
                cell_control: ft.Control = content
            else:
                cell_control = ft.Container(
                    content=content,
                    width=widths[key],
                    alignment=ft.Alignment.CENTER,
                )

            cells.append(
                ft.DataCell(
                    cell_control,
                    on_double_tap=(
                        (
                            lambda event, r=record: (
                                self._open_edit_entry_form(r)
                            )
                        )
                        if (
                            key == "number"
                            and not self.preferences.merge_same_anime
                        )
                        else None
                    ),
                    on_long_press=(
                        (
                            lambda event, r=record: (
                                self._open_insert_entry_form(r)
                            )
                        )
                        if (
                            key == "number"
                            and not self.sort_column
                            and not self._active_filters()
                            and not self.preferences.merge_same_anime
                        )
                        else None
                    ),
                )
            )
        return ft.DataRow(cells=cells)

    def _column_width(
        self,
        key: str,
        label: str,
        page_records: list[Record],
        start: int,
    ) -> int:
        # 测量真实渲染文本，而不是按字符数估算：
        # 这样长拉丁标题能完整显示，也不会在
        # 其他每一行留下大片空白。
        longest = text_width(label, bold=True)
        if key == "number":
            longest = max(
                longest,
                text_width(str(start + len(page_records))),
            )
        elif key == "entry":
            for record in page_records:
                value = str(
                    record.get("entry") or record.get("anime") or ""
                )
                longest = max(longest, text_width(value))
        elif key == "tag":
            for record in page_records:
                tags = split_tags(
                    str(record.get("tag", "") or "")
                )
                if not tags:
                    continue
                row_width = sum(
                    text_width(tag, size=12) + 20
                    for tag in tags
                )
                row_width += 4 * (len(tags) - 1) + 10
                longest = max(longest, row_width)
        else:
            for record in page_records:
                value = str(record.get(key, ""))
                if key == "role":
                    value = first_role_name(value)
                elif key == "remark":
                    value = truncate_display(value, 100)
                longest = max(
                    longest,
                    text_width(value),
                )

        width = max(
            MIN_COLUMN_WIDTH,
            math.ceil(longest * (1 + COLUMN_TEXT_SAFETY_RATIO))
            + COLUMN_TEXT_PADDING,
        )
        if key == "tag":
            width = max(width, 120)
        elif key == "entry":
            width = max(120, min(320, width))
        return width

    def _visible_column_labels(self) -> list[tuple[str, str]]:
        labels = dict(WATCHED_COLUMNS)
        columns = [
            (key, labels[key])
            for key in self.column_order
            if self.visible_columns.get(key, True) and key in labels
        ]
        if self.preferences.merge_same_anime:
            position = 0
            for offset, (key, _) in enumerate(columns):
                if key == "number":
                    position = offset + 1
                    break
            columns.insert(position, ("entry", "条目"))
        return columns

    def _menu_columns(self) -> list[tuple[str, str]]:
        labels = dict(WATCHED_COLUMNS)
        return [
            (key, labels[key])
            for key in self.column_order
            if key != "number" and key in labels
        ]

