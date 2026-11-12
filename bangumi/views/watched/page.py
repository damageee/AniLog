"""观影表格页。"""

from __future__ import annotations

import asyncio
import random
import re
import shutil
from pathlib import Path

import flet as ft

from bangumi.io.exporter import build_workbook_bytes
from bangumi.io.importer import import_records
from bangumi.data.preferences import Preferences
from bangumi.data.sorting import (
    completion_sort_key,
    sort_key,
    specification_sort_key,
)
from bangumi.core.storage import table_file
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.feedback import (
    show_error_dialog,
)
from bangumi.ui.interaction import (
    back_icon,
    hover_icon,
    is_attached,
)
from bangumi.ui import scroll_memory
from bangumi.ui.layout import (
    page_padding,
)
from bangumi.ui.constants import DIVIDER_OPACITY
from bangumi.views.navigation import (
    ENTRY,
)
from bangumi.views.settings.help import open_help
from bangumi.views.navigation import open_detail
from bangumi.views.widgets.toast import show_toast
from bangumi.views.widgets.file_picker import ensure_file_picker
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.data.watched_data import (
    Record,
    entry_group_key,
    load_records,
    save_records,
    sync_sequel_groups,
)


from bangumi.views.watched.constants import *
from bangumi.views.watched.state import view_state
from bangumi.views.watched.table import TableMixin
from bangumi.views.watched.search import SearchMixin
from bangumi.views.watched.filters import FilterMixin
from bangumi.views.watched.pagination import PaginationMixin
from bangumi.views.watched.options import OptionsMixin
from bangumi.views.watched.records import RecordsMixin
from bangumi.views.watched.actions import ActionsMixin


class WatchedPage(TableMixin, SearchMixin, FilterMixin, PaginationMixin, OptionsMixin, RecordsMixin, ActionsMixin):
    """观影表格页的状态与 UI。"""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.state = view_state(page)
        self.state.horizontal_offset = 0.0
        self.state.vertical_offset = 0.0
        scroll_memory.prune(page)
        self.preferences = Preferences.load()
        self.table_exists = table_file().is_file()
        self.records = load_records() if self.table_exists else []
        self._records_version = 0
        sync_tag_colors(self.records, self.preferences)
        self.current_page = self.state.current_page
        self.anchor_positions: dict[str, float] = {}
        self.table_scroll: ft.Row | None = None
        self.table_body: ft.Column | None = None
        self._restoring_scroll = False
        self._scroll_future = None
        self._scroll_generation = 0
        self._scroll_target: tuple[float, float, bool] = (0.0, 0.0, False)
        self.search_query = ""
        self.filters: list[list[str]] = []
        self.filter_column = ft.Column(spacing=6, controls=[])
        self._applied_filters: list[tuple[str, str]] = []
        self.search_results: list[tuple[int, str, int, int, int]] = []
        self.search_current = -1
        self._search_token = 0
        self._last_visible_keys: list[str] = []
        self._last_widths: dict[str, int] = {}
        self._last_row_heights: list[float] = []
        self._last_table_width = 0.0
        self._duplicate_prompt_queue: list[str] = []
        self._duplicate_prompt_token: object | None = None
        self.pending_manual: list[tuple[int, str, list[dict]]] = []
        self._fill_running = False
        self._fill_abort = False

        self.page_number_input = self._create_page_number_input()
        self.page_size_input = self._create_page_size_input()
        self.picker = ensure_file_picker(self.page)
        self.search_field = self._create_search_field()
        self.search_box = self._create_search_box()
        (
            self.search_prev_button,
            self.search_next_button,
        ) = self._create_search_buttons()
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        self.search_count = ui_text(
            "",
            size=13,
            color=ft.Colors.GREY_400 if dark else ft.Colors.GREY_600,
            width=90,
            no_wrap=True,
            text_align=ft.TextAlign.LEFT,
        )
        self.search_row = self._create_search_row()
        self.header = ft.Column(spacing=10, controls=[])
        self.body = ft.Column(
            expand=True,
            spacing=5,
            scroll=ft.ScrollMode.AUTO,
            on_scroll=self._record_vertical_offset,
        )
        self.view = self._create_view()
        self._previous_on_resize = self.page.on_resize
        self.page.on_resize = self._on_resize
        self.refresh(update_page=False, update_header=True)

    def _on_resize(self, event: ft.ControlEvent | None = None) -> None:
        if self.view in self.page.views:
            try:
                self.page.update()
            except RuntimeError:
                return
        previous = self._previous_on_resize
        if previous is not None and previous is not self._on_resize:
            previous(event)

    @property
    def page_size(self) -> int:
        return self.preferences.page_size

    @property
    def column_order(self) -> list[str]:
        return self.preferences.column_order

    @property
    def visible_columns(self) -> dict[str, bool]:
        return self.preferences.visible_columns

    @property
    def sort_column(self) -> str:
        return self.preferences.sort_column

    @property
    def sort_ascending(self) -> bool:
        return self.preferences.sort_ascending

    def reload(self) -> None:
        """就地重新加载数据并重建页面内容。

        不调用 ``page.update()``；由调用方统一更新一次。
        """
        self.preferences = Preferences.load()
        self.table_exists = table_file().is_file()
        self.records = load_records() if self.table_exists else []
        self._records_version = (
            getattr(self, "_records_version", 0) + 1
        )
        sync_tag_colors(self.records, self.preferences)
        try:
            self._recompute_search()
        except Exception:
            pass
        self.refresh(update_page=False, update_header=True)
        self._schedule_scroll_restore()

    def refresh(
        self,
        *,
        update_page: bool = True,
        reset_scroll: bool = False,
        preserve_vertical: bool = False,
        restore_scroll: bool = True,
        update_header: bool = False,
    ) -> None:
        if reset_scroll:
            self.state.horizontal_offset = 0.0
            if not preserve_vertical:
                self.state.vertical_offset = 0.0

        self.current_page = min(
            self.current_page,
            self._total_pages() - 1,
        )
        self.state.current_page = self.current_page
        self.page_number_input.value = str(self.current_page + 1)
        self.page_number_input.error_text = None
        if self.page_size_input.value != str(self.page_size):
            self.page_size_input.value = str(self.page_size)
        self.page_size_input.error_text = None

        if update_header:
            if self.search_field.value != self.search_query:
                self.search_field.value = self.search_query
            header_controls: list[ft.Control] = [self._action_buttons()]
            if self.table_exists:
                header_controls.append(self.search_row)
            self.header.controls = header_controls

        controls: list[ft.Control] = []
        if self.table_exists:
            controls.extend(
                [
                    self._table_scroll_area(),
                    self._pagination_row(),
                    ft.Container(
                        height=1,
                        width=(
                            self._last_table_width
                            or max(
                                200.0,
                                float(self.page.width or 1000) - 48,
                            )
                        ),
                        bgcolor=ft.Colors.with_opacity(
                            DIVIDER_OPACITY,
                            foreground_color(self.page),
                        ),
                    ),
                    self._filter_section(),
                    ft.Row(
                        alignment=(
                            ft.MainAxisAlignment.CENTER
                            if is_compact_layout(self.page)
                            else ft.MainAxisAlignment.START
                        ),
                        spacing=8,
                        vertical_alignment=(
                            ft.CrossAxisAlignment.CENTER
                        ),
                        controls=[
                            hover_icon(
                                self.page,
                                ft.Icons.CASINO,
                                tooltip="随机打开动画",
                                disabled=not self.records,
                                on_click=(
                                    lambda event: (
                                        self._open_random_entry()
                                    )
                                ),
                            ),
                            ft.Button(
                                content=ui_text("使用说明"),
                                on_click=(
                                    lambda event: open_help(self.page)
                                ),
                            ),
                        ],
                    ),
                    self._options_row(),
                    self._page_size_row(),
                    ft.Row(
                        alignment=(
                            ft.MainAxisAlignment.CENTER
                            if is_compact_layout(self.page)
                            else ft.MainAxisAlignment.START
                        ),
                        controls=[
                            ft.Button(
                                content=ui_text("从Bangumi填充表格"),
                                on_click=self._open_fill_dialog,
                            )
                        ],
                    ),
                ]
            )
        else:
            self.table_scroll = None
            self.table_body = None
            self._table_scroll_row = None
            self._table_header_table = None
            self._table_body_table = None
            self._table_header_sig = None
            self._table_rows_sig = None
            self._table_layout_sig = None
            self._table_row_cache = {}
        controls.append(ft.Container(height=24))
        self.body.controls = controls
        if update_page:
            if update_header:
                self.page.update(self.header, self.body)
            else:
                self.body.update()
            if restore_scroll:
                self._schedule_scroll_restore(force=reset_scroll)

    def _create_view(self) -> ft.View:
        return ft.View(
            route="/watched",
            appbar=ft.AppBar(
                title=ui_text("已阅"),
                automatically_imply_leading=False,
                leading=back_icon(self.page, "/"),
            ),
            padding=page_padding(),
            controls=[self.header, self.body],
        )

    def _schedule_scroll_restore(self, *, force: bool = False) -> None:
        horizontal = self.state.horizontal_offset
        vertical = self.state.vertical_offset
        running = (
            self._scroll_future is not None
            and not self._scroll_future.done()
        )
        if not force and horizontal == 0 and vertical == 0 and not running:
            return

        # 一个防抖循环负责所有恢复：快速翻页时只更新
        # 目标，而不会创建重叠任务。
        self._scroll_generation += 1
        self._scroll_target = (horizontal, vertical, force)
        self._restoring_scroll = True
        if not running:
            self._scroll_future = self.page.run_task(
                self.restore_scroll_position
            )

    async def restore_scroll_position(self) -> None:
        # 恢复滚动位置是尽力而为：失败绝不能
        # 中断页面渲染。
        try:
            while True:
                generation = self._scroll_generation
                await asyncio.sleep(0.1)
                if generation != self._scroll_generation:
                    continue

                horizontal, vertical, force = self._scroll_target

                mounted = False
                for _ in range(3):
                    if any(view is self.view for view in self.page.views):
                        mounted = True
                        break
                    await asyncio.sleep(0.1)
                    if generation != self._scroll_generation:
                        break
                if generation != self._scroll_generation:
                    continue
                if not mounted:
                    break

                if (
                    is_attached(self.table_scroll)
                    and (force or horizontal > 0)
                ):
                    try:
                        await self.table_scroll.scroll_to(
                            offset=horizontal,
                            duration=0,
                        )
                    except Exception:
                        pass

                if (
                    is_attached(self.body)
                    and (force or vertical > 0)
                ):
                    try:
                        await self.body.scroll_to(
                            offset=vertical,
                            duration=0,
                        )
                    except Exception:
                        pass

                if generation == self._scroll_generation:
                    break
        finally:
            self._scroll_future = None
            self._restoring_scroll = False

    def _completion_month(self, value: str) -> tuple[int, int] | None:
        match = re.match(r"\s*(\d{4})[.\-/年](\d{1,2})", value or "")
        if not match:
            return None
        year = int(match.group(1))
        month = int(match.group(2))
        if not (1 <= month <= 12):
            return None
        return year, month

    def _open_completion_month(self, key: tuple[int, int]) -> None:
        from bangumi.views.statistics import open_month_completion

        open_month_completion(self.page, key[0], key[1])

    def _merge_key(self, record: Record) -> str:
        return entry_group_key(record) or f"__{id(record)}"

    def _sorted_records(
        self,
        *,
        filtered: bool = True,
    ) -> list[Record]:
        base = self._filtered_records() if filtered else self.records
        if not self.sort_column:
            return base
        if self.sort_column == "completion":
            key_func = completion_sort_key
        elif self.sort_column == "specification":
            key_func = specification_sort_key
        else:
            key_func = sort_key
        return sorted(
            base,
            key=lambda record: key_func(
                str(record.get(self.sort_column, ""))
            ),
            reverse=not self.sort_ascending,
        )

    def _display_records(
        self,
        *,
        filtered: bool = True,
    ) -> list[Record]:
        base = self._sorted_records(filtered=filtered)
        if not self.preferences.merge_same_anime:
            return base

        groups: dict[str, list[Record]] = {}
        order: list[str] = []
        for record in base:
            key = self._merge_key(record)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(record)
        return [record for key in order for record in groups[key]]

    def _open_random_entry(self) -> None:
        records = self._display_records()
        if not records:
            return
        record = random.choice(records)
        open_detail(self.page, self.records, record, ENTRY)

    def _open_fill_dialog(self, event: ft.ControlEvent) -> None:
        from bangumi.views.watched.fill_table import open_fill_dialog

        open_fill_dialog(self)

    async def _scroll_to_search_result(
        self,
        token: int,
        record_index: int,
        column_key: str,
    ) -> None:
        try:
            await asyncio.sleep(0.1)
            if token != self._search_token:
                return
            keys = self._last_visible_keys
            widths = self._last_widths
            if (
                self.table_scroll is not None
                and getattr(self.table_scroll, "page", None) is not None
                and column_key in keys
            ):
                index = keys.index(column_key)
                center = (
                    sum(
                        widths[key] + 4
                        for key in keys[:index]
                    )
                    + widths[column_key] / 2
                )
                viewport = max(
                    0,
                    int((self.page.width or 900) - 48),
                )
                await self.table_scroll.scroll_to(
                    offset=max(0.0, center - viewport / 2),
                    duration=0,
                )
            row = record_index % self.page_size
            heights = self._last_row_heights
            if 0 <= row < len(heights):
                y = sum(heights[:row])
            else:
                y = row * DATA_ROW_HEIGHT
            target = self.table_body
            if is_compact_layout(self.page) or target is None:
                target = self.body
                y += 14 + 48
            if getattr(target, "page", None) is not None:
                await target.scroll_to(
                    offset=max(0.0, y - 80),
                    duration=0,
                )
        except Exception:
            pass

    def _sort_by(self, key: str) -> None:
        if self.sort_column == key:
            self.preferences.sort_ascending = not self.sort_ascending
        else:
            self.preferences.sort_column = key
            self.preferences.sort_ascending = False
        self.preferences.save()
        if self.search_query:
            self._resync_search(reset_scroll=True)
        else:
            self.current_page = 0
            self.refresh(reset_scroll=True)

    def move_column(
        self,
        source_key: str | None,
        target_key: str,
        after: bool = False,
    ) -> None:
        if (
            not source_key
            or source_key == target_key
            or source_key == "number"
            or target_key == "number"
        ):
            return
        if source_key not in self.column_order:
            return
        if target_key not in self.column_order:
            return

        order = self.column_order
        source_index = order.index(source_key)
        target_index = order.index(target_key)
        order.pop(source_index)
        if source_index < target_index:
            target_index -= 1
        if after:
            target_index += 1
        # 序号始终位于第一列。
        target_index = min(max(target_index, 1), len(order))
        order.insert(target_index, source_key)
        self.preferences.save()
        self._resync_search()

    async def _save_export_bytes(self, data: bytes) -> str | None:
        path = await self.picker.save_file(
            dialog_title="导出 Watched 表格",
            file_name="bangumi.xlsx",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
            src_bytes=data,
        )
        if path is None:
            raise ValueError("未选择保存路径，导出未完成")

        source = Path(str(path))
        raw_path = str(path)
        if not raw_path.endswith(".") and source.suffix:
            if not source.is_file():
                raise FileNotFoundError(
                    f"导出的文件不存在：{source}"
                )
            return raw_path

        if raw_path.endswith("."):
            target = Path(raw_path + "xlsx")
        else:
            target = Path(raw_path + ".xlsx")

        if target.exists():
            raise FileExistsError(f"目标文件已存在：{target}")
        try:
            shutil.move(str(source), str(target))
        except OSError as error:
            raise OSError(f"移动导出文件失败：{error}") from error
        return str(target)

    async def _export_table(self, event: ft.ControlEvent) -> None:
        try:
            records = self._display_records()
            columns = [
                (key, label)
                for key, label in self._visible_column_labels()
                if key != "number"
            ]
            if not self.preferences.merge_same_anime:
                columns = [
                    ("entry", "条目"),
                    *[
                        (key, label)
                        for key, label in columns
                        if key != "entry"
                    ],
                ]
            data = build_workbook_bytes(
                records,
                columns,
                self.preferences.merge_same_anime,
            )

            path = await self._save_export_bytes(data)
            if path is None:
                return
            show_toast(self.page, f"已导出到 {path}")
        except Exception as error:
            show_error_dialog(
                self.page,
                title="导出失败",
                message=str(error),
            )

    async def _import_table(self, event: ft.ControlEvent) -> None:
        try:
            selected_files = await self.picker.pick_files(
                dialog_title="导入 Watched 表格",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["csv", "xls", "xlsx"],
                allow_multiple=False,
                with_data=True,
            )
            if not selected_files:
                return

            selected_file = selected_files[0]
            file_bytes = selected_file.bytes
            if file_bytes is None and selected_file.path:
                file_bytes = Path(selected_file.path).read_bytes()
            if file_bytes is None:
                raise ValueError("无法读取所选文件")

            imported_records, cleaning = import_records(
                file_bytes,
                selected_file.name,
            )
            if not imported_records:
                raise ValueError("没有可导入的记录")
            updated_records = [*self.records, *imported_records]
            sync_sequel_groups(updated_records)
            save_records(updated_records)
            self.records = updated_records
            self._records_version = (
                getattr(self, "_records_version", 0) + 1
            )
            sync_tag_colors(self.records, self.preferences)
            self.table_exists = True
            if self.search_query:
                self._resync_search(
                    reset_scroll=True,
                    update_header=True,
                )
            else:
                self.current_page = max(0, self._total_pages() - 1)
                self.refresh(reset_scroll=True, update_header=True)
            lines = [
                f"共导入 {len(imported_records)} 条",
                f"缺少动画名：{cleaning['missing_anime']} 条",
                f"规格为空：{cleaning['missing_spec']} 条",
                f"放送为空：{cleaning['missing_broadcast']} 条",
                f"类型为空（已归入其他）：{cleaning['missing_category']} 条",
                f"动画名重复（导入文件内）：{cleaning['duplicate_anime']} 条",
                f"放送日期格式错误：{cleaning['invalid_broadcast']} 条",
                f"补完日期格式错误：{cleaning['invalid_completion']} 条",
                f"类型不合法（已归入其他）：{cleaning['invalid_category']} 条",
                f"评分不合法：{cleaning['invalid_rating']} 条",
            ]
            dialog = ft.AlertDialog(
                title=ui_text("导入完成"),
                content=ft.Column(
                    tight=True,
                    spacing=6,
                    controls=[ui_text(line, size=13) for line in lines],
                ),
                actions=[],
            )
            dialog.actions = [
                ft.Button(
                    content=ui_text("关闭"),
                    on_click=lambda event: self.page.pop_dialog(),
                )
            ]
            self.page.show_dialog(dialog)
        except Exception as error:
            show_error_dialog(
                self.page,
                title="导入失败",
                message=str(error),
            )


def watched_view(page: ft.Page) -> ft.View:
    instance = WatchedPage(page)
    instance._schedule_scroll_restore()

    def rebuild() -> ft.View:
        query = instance.search_query
        new = WatchedPage(page)
        try:
            new.search_query = query
            new.search_field.value = query
            new._recompute_search()
            new.refresh(update_header=True)
        except Exception:
            pass
        try:
            new._schedule_scroll_restore()
        except Exception:
            pass
        return new.view

    instance.view.data = {
        "refresh": instance.reload,
        "rebuild": rebuild,
    }
    return instance.view

