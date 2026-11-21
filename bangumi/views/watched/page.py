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
from bangumi.ui.platform import is_compact_layout, is_mobile
from bangumi.ui.theme import (
    ui_text,
    ui_text_style,
)
from bangumi.ui.colors import foreground_color
from bangumi.ui.feedback import (
    show_error_dialog,
)
from bangumi.ui.interaction import (
    back_icon,
    hover_icon,
    hover_link,
    is_attached,
)
from bangumi.ui.events import is_hover
from bangumi.ui import scroll_memory
from bangumi.ui.layout import (
    page_padding,
)
from bangumi.ui.text_metrics import text_width
from bangumi.core.cover_proc import processed_cover
from bangumi.views.general.detail_staff import open_staff_page
from bangumi.views.navigation import (
    CATEGORY,
    ENTRY,
    TAG,
)
from bangumi.views.widgets.links import BroadcastLink, StudioLink, highlight_spans
from bangumi.views.widgets.image_preview import show_image_preview
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.views.settings.help import open_help
from bangumi.views.navigation import open_detail
from bangumi.views.widgets.toast import show_toast
from bangumi.views.widgets.file_picker import ensure_file_picker
from bangumi.ui.tag_colors import sync_tag_colors


# 已阅页搜索命中高亮：浅绿底，文字保持原色。
SEARCH_HIGHLIGHT_BG = "#FDE68A"
SEARCH_ACTIVE_BG = "#BBF7D0"
from bangumi.data.watched_data import (
    Record,
    WATCHED_COLUMNS,
    entry_group_key,
    load_records,
    save_records,
    record_title,
    split_tags,
    staff_display,
    sync_sequel_groups,
)
from bangumi.data.quarter_core import earliest_broadcast_date


from bangumi.views.watched.constants import *
from bangumi.views.watched.state import (
    WatchedViewState,
    bind_view_state,
)
from bangumi.views.watched.table import TableMixin
from bangumi.views.watched.search import SearchMixin, display_broadcast
from bangumi.views.watched.filters import FilterMixin
from bangumi.views.watched.pagination import PaginationMixin
from bangumi.views.watched.options import OptionsMixin
from bangumi.views.watched.records import RecordsMixin
from bangumi.views.watched.actions import ActionsMixin


# 筛选 chip 的中文标签。
_FILTER_LABELS = {
    "category": "类型",
    "tag": "TAG",
    "studio": "制作",
    "year": "年份",
    "rating": "评分",
}


class WatchedPage(TableMixin, SearchMixin, FilterMixin, PaginationMixin, OptionsMixin, RecordsMixin, ActionsMixin):
    """观影表格页的状态与 UI。"""

    def __init__(
        self,
        page: ft.Page,
        state: WatchedViewState | None = None,
    ) -> None:
        self.page = page
        # 按当前主题构建一次颜色表。
        self._ui_colors = self._build_colors()
        self._layout_width = float(page.width or 1000)
        # 同一 View 的重建共享状态；新实例使用全新状态。
        self.state = state if state is not None else WatchedViewState()
        # 保留上次的滚动位置，构造时不清零。
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
        self._horizontal_syncing = False
        self._restoring_scroll = False
        self._last_restore_pixels: float | None = None
        # 排序时按新旧横向滚动范围的比例换算偏移。
        self._restore_ratio: float | None = None
        self._scroll_future = None
        self._scroll_generation = 0
        self._scroll_target: tuple[float, float, bool] = (0.0, 0.0, False)
        self.search_query = ""
        self.filters: list[list[str]] = []
        self._applied_query: str | None = None
        self._rendered_query = ""
        self._last_hit_current = -1
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
            on_scroll=(
                lambda event: self._record_vertical_offset(
                    event, "page"
                )
            ),
        )
        # 注册页面整体滚动的记忆，由 go_back 统一恢复。
        scroll_memory.remember(
            self.page, "/watched", "body", self.body
        )
        self.view = self._create_view()
        bind_view_state(self.view, self.state)
        register_resize_handler(self.page, "/watched", self._on_resize)
        self.refresh(update_page=False, update_header=True)
        # 构造完成后恢复上次的滚动位置（若有）。
        if (
            self.state.horizontal_offset
            or self.state.vertical_offset
        ):
            self._schedule_scroll_restore(force=True)

    def _reselect_search_after_layout(self) -> None:
        """布局变化后重算结果，并选中离旧结果最近的可用结果。"""
        old = None
        if 0 <= self.search_current < len(self.search_results):
            old = self.search_results[self.search_current][:4]
        self._recompute_search()
        results = self.search_results
        if not results:
            self.search_current = -1
            self._update_search_buttons()
            return

        columns = self._search_columns()
        order = {key: index for index, key in enumerate(columns)}

        def sort_key(item: tuple) -> tuple:
            return (
                item[0],
                order.get(item[1], len(columns)),
                item[2],
                item[3],
            )

        if old is None:
            self.search_current = 0
        else:
            exact = next(
                (
                    index
                    for index, item in enumerate(results)
                    if item[:4] == old
                ),
                None,
            )
            if exact is not None:
                self.search_current = exact
            else:
                old_key = (
                    old[0],
                    order.get(old[1], len(columns)),
                    old[2],
                    old[3],
                )
                before = [
                    index
                    for index, item in enumerate(results)
                    if sort_key(item) < old_key
                ]
                self.search_current = before[-1] if before else 0
        self._update_search_buttons()

    def current_width(self) -> float:
        """优先使用 on_resize 记录的最新宽度。"""
        size = getattr(self.page, "_resize_last_size", None)
        if isinstance(size, dict) and size.get("w"):
            return float(size["w"])
        return float(self.page.width or 1000)

    def _anim_avail(self, width: float) -> float:
        """桌面动画列可用文本宽度（按当前可见列估算）。"""
        content_w = max(280.0, width - 48.0)
        show_studio = width >= 1100.0
        show_completion = width >= 900.0
        count = 3 + int(show_studio) + int(show_completion)
        fixed = 140.0 + 40.0 + 24.0 + 12.0 * (count - 1)
        units = 4.0 + (2.0 if show_studio else 0.0)
        units += 1.0 if show_completion else 0.0
        anim_col = max(160.0, content_w - fixed) * 3.0 / units
        return max(120.0, anim_col - 48.0 - 12.0)

    def _on_resize(self, event: ft.ControlEvent | None = None) -> None:
        # 仅栈顶响应；延迟到停手后再统一处理一次。
        if (
            not self.page.views
            or self.page.views[-1] is not self.view
        ):
            return
        width = self.current_width()
        if abs(
            width - float(getattr(self, "_layout_width", width))
        ) < 2:
            return
        self._resize_token = getattr(self, "_resize_token", 0) + 1
        token = self._resize_token
        try:
            self.page.run_task(self._apply_resize, token)
        except RuntimeError:
            return

    async def _apply_resize(self, token: int) -> None:
        await asyncio.sleep(0.15)
        if token != getattr(self, "_resize_token", 0):
            return
        if getattr(self, "_resizing", False):
            return
        if (
            not self.page.views
            or self.page.views[-1] is not self.view
        ):
            return
        self._resizing = True
        try:
            width = self.current_width()
            bucket = (
                "mobile" if width < 760
                else (
                    "mid" if width < 900
                    else ("compact" if width < 1100 else "full")
                )
            )
            columns = tuple(self._search_columns())
            layout_changed = (
                bucket != getattr(self, "_layout_bucket", None)
                or columns
                != getattr(self, "_layout_search_columns", None)
            )
            if layout_changed:
                # 断点或可见列变化：先重算搜索并重选。
                self._layout_bucket = bucket
                self._layout_search_columns = columns
                self._reselect_search_after_layout()
            old_width = float(
                getattr(self, "_layout_width", width)
            )
            old_extent = float(
                getattr(self.state, "vertical_max_extent", 0.0)
                or 0.0
            )
            old_offset = float(
                getattr(self.state, "vertical_offset", 0.0)
                or 0.0
            )
            was_at_bottom = (
                old_extent > 0 and old_offset >= old_extent - 2
            )
            widened = width > old_width + 2
            self._layout_width = width
            try:
                self.refresh(
                    update_header=layout_changed,
                    restore_scroll=False,
                )
            except Exception:
                pass
            self._layout_width = self.current_width()
            if widened and was_at_bottom:
                # 变宽后内容变短：不再用旧 offset，等布局稳定后只兜底一次。
                await asyncio.sleep(0.25)
                if token != self._resize_token:
                    return
                extent = float(
                    getattr(
                        self.state,
                        "vertical_max_extent",
                        0.0,
                    )
                    or 0.0
                )
                offset = float(
                    getattr(
                        self.state,
                        "vertical_offset",
                        0.0,
                    )
                    or 0.0
                )
                if extent > 0 and offset < extent - 4:
                    owner = getattr(
                        self.state,
                        "vertical_owner",
                        "page",
                    )
                    target = (
                        self.table_body
                        if owner == "table"
                        else self.body
                    )
                    if target is not None:
                        try:
                            await target.scroll_to(
                                offset=extent,
                                duration=0,
                            )
                            self.state.vertical_offset = extent
                        except Exception:
                            pass
                return
            # 其它情况仍走一次统一恢复；restore 内会先 clamp。
            await asyncio.sleep(0.15)
            if token == self._resize_token:
                self._schedule_scroll_restore(force=True)
            return
        except RuntimeError:
            return
        finally:
            self._resizing = False

    @property
    def page_size(self) -> int:
        return self.preferences.page_size

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

        total_pages = self._total_pages()
        # 空数据或只有一页时不钳制，避免编辑保存后页码被压回第 1 页。
        if self.records and total_pages > 1:
            self.current_page = min(
                self.current_page,
                total_pages - 1,
            )
            self.state.current_page = self.current_page
        self.page_number_input.value = str(self.current_page + 1)
        self.page_number_input.error_text = None
        if self.page_size_input.value != str(self.page_size):
            self.page_size_input.value = str(self.page_size)
        self.page_size_input.error_text = None

        self.count_text.value = f"{len(self.records)} 部"
        if update_header:
            if self.search_field.value != self.search_query:
                self.search_field.value = self.search_query
            # 新骨架：工具栏卡片（搜索 + 筛选 chips + 筛选/显示）。
            self.header.controls = [self._toolbar_card()]

        # 新骨架：只渲染工具栏、表格卡与分页卡。
        if self.table_exists:
            self.body.scroll = ft.ScrollMode.AUTO
            self.body.controls = [
                self._table_card(),
                self._pagination_card(),
            ]
        else:
            self.body.scroll = ft.ScrollMode.AUTO
            self.body.controls = [self._empty_card()]
        # 排序后按旧/新横向范围的比例换算偏移，再交给恢复任务。
        if self._restore_ratio is not None:
            self.state.horizontal_offset = (
                max(0.0, min(1.0, self._restore_ratio))
                * getattr(self, "_last_h_extent", 0.0)
            )
            self._restore_ratio = None
        if update_page:
            if update_header:
                self.page.update(self.header, self.body)
            else:
                self.body.update()
            if restore_scroll:
                self._schedule_scroll_restore(force=reset_scroll)

    def _install_search_keys(self) -> None:
        """Shift+回车 = 上一条；链式保留原键盘处理。"""
        previous = self.page.on_keyboard_event

        def on_keyboard(event: ft.KeyboardEvent) -> None:
            key = str(getattr(event, "key", "") or "")
            shift = bool(getattr(event, "shift", False))
            if (
                shift
                and key in ("Enter", "Numpad Enter")
                and getattr(self, "_search_focused", False)
                and not getattr(self, "_shift_busy", False)
            ):
                self._shift_busy = True
                try:
                    # 取消挂起的防抖搜索，走上一条。
                    self._search_token += 1
                    self._skip_next_submit = True
                    self._step_search(-1)
                    self.page.run_task(self._refocus_search)
                finally:
                    self._shift_busy = False
            if callable(previous):
                previous(event)

        self.page.on_keyboard_event = on_keyboard

    def _update_search_rows(self, record_index: int) -> None:
        """同页切换命中：满足条件才只重绘新旧两行。"""
        controls = getattr(self, "_row_controls", None)
        body = self.table_body
        display = self._display_records()
        self._render_display = display
        start = self.current_page * self.page_size
        page_rows = display[start : start + self.page_size]
        local_new = record_index - start
        old = getattr(self, "_active_row_index", -1)
        previous = getattr(self, "_last_hit_current", -1)
        # 只有纯粹的命中切换才走两行重绘，否则全量刷新。
        can_patch = (
            self.search_query
            == getattr(self, "_rendered_query", None)
            and controls
            and len(controls) == len(page_rows)
            and old >= 0
            and previous >= 0
            and body is not None
        )
        if not can_patch:
            self.refresh(restore_scroll=False)
            self._last_hit_current = self.search_current
            return
        for local in {old, local_new}:
            if (
                0 <= local < len(controls)
                and 0 <= start + local < len(display)
            ):
                controls[local] = self._watched_row(
                    display[start + local]
                )
        body.controls = controls
        try:
            body.update()
        except Exception:
            pass
        self._active_row_index = local_new
        self._last_hit_current = self.search_current

    def _build_colors(self) -> dict[str, str]:
        """按当前主题计算颜色；不在模块级写死。"""
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        return {
            "page_bg": "#111418" if dark else "#F7F8FA",
            "card_bg": "#1E2228" if dark else "#FFFFFF",
            "border": "#2A2F36" if dark else "#E5E8EE",
            "text": foreground_color(self.page),
            "secondary": "#9CA3AF" if dark else "#6B7280",
            "chip_bg": "#2A2F36" if dark else "#EEF2F7",
            "chip_fg": "#D1D5DB" if dark else "#4B5563",
            "hover_bg": "#262B32" if dark else "#F5F7FA",
            "field_bg": "#15181D" if dark else "#FFFFFF",
            "head_bg": "#232830" if dark else "#FAFBFC",
            "add_bg": "#2A2F36" if dark else "#DCE9F8",
            "add_fg": "#E5E7EB" if dark else "#1F2430",
        }

    def _create_view(self) -> ft.View:
        # 标题紧跟返回箭头；加号 / … / 骰子排在标题右侧，等距。
        self.count_text = ui_text("", size=12, color=self._ui_colors["secondary"])
        add_button = ft.Container(
            bgcolor=self._ui_colors["add_bg"],
            border_radius=999,
            content=hover_icon(
                self.page,
                ft.Icons.ADD,
                tooltip="追加",
                color=self._ui_colors["text"],
                size=18,
                padding=6,
                on_click=lambda e: self._open_create_entry_form(),
            ),
        )
        title_row = ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=0,
                    controls=[
                        ui_text(
                            "已阅",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=self._ui_colors["text"],
                        ),
                        self.count_text,
                    ],
                ),
                add_button,
                self._more_menu(),
                hover_icon(
                    self.page,
                    ft.Icons.CASINO,
                    tooltip="随机打开动画",
                    on_click=lambda e: self._open_random_entry(),
                    size=18,
                    padding=6,
                ),
            ],
        )
        view = ft.View(
            route="/watched",
            bgcolor=self._ui_colors["page_bg"],
            appbar=ft.AppBar(
                bgcolor=self._ui_colors["card_bg"],
                leading=back_icon(self.page, "/"),
                automatically_imply_leading=False,
                title=title_row,
            ),
            padding=page_padding(),
            controls=[self.header, self.body],
        )
        # view_cache 重新挂回控件时触发滚动恢复。
        data = view.data if isinstance(view.data, dict) else {}
        data["on_restore"] = (
            lambda: self._schedule_scroll_restore(force=True)
        )
        # 已阅页保持客户端挂载，滚动位置由客户端自然保留。
        data["keep_alive"] = True
        data["on_shown"] = self._on_shown
        data["on_close"] = self._reset_view_state
        view.data = data
        return view

    async def _scroll_body_to(self, offset: float) -> None:
        target = self.body
        if self.table_exists and not is_mobile(self.page):
            target = self.table_body
        if target is None:
            return
        try:
            await target.scroll_to(offset=offset, duration=0)
        except Exception:
            pass

    def _reset_view_state(self) -> None:
        """被移出视图栈（返回首页）时清空页码与滚动记录。"""
        self.state.current_page = 0
        self.state.vertical_offset = 0.0
        self.state.horizontal_offset = 0.0
        self.state.vertical_max_extent = 0.0
        self.state.horizontal_max_extent = 0.0
        self.current_page = 0
        scroll_memory.prune(self.page)

    def _clamp_page(self) -> bool:
        """页码超出总页数时收束到最后一页；返回是否发生收束。"""
        pages = max(1, self._total_pages())
        if self.current_page <= pages - 1:
            return False
        self.current_page = pages - 1
        self.state.current_page = self.current_page
        self.state.vertical_offset = 0.0
        self.state.horizontal_offset = 0.0
        return True

    def _on_shown(self) -> None:
        """返回已阅页：先收束页码，再恢复滚动。"""
        if self._clamp_page():
            self.refresh()
            return
        self._schedule_scroll_restore(force=True)

    def _schedule_scroll_restore_force(self) -> None:
        """供 on_shown / on_restore 使用的无参恢复入口。"""
        self._schedule_scroll_restore(force=True)

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
        if not running and self._restoring_scroll:
            # 上一次任务已经结束，清掉可能卡住的恢复标志。
            self._restoring_scroll = False
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

                if force or vertical > 0:
                    owner = getattr(
                        self.state, "vertical_owner", "page"
                    )
                    target = (
                        self.table_body
                        if owner == "table"
                        else self.body
                    )
                    # 最多 2 次；每次重新读取 extent 后再收束。
                    for _ in range(2):
                        vertical = max(
                            0.0,
                            float(self.state.vertical_offset),
                        )
                        extent = float(
                            getattr(
                                self.state,
                                "vertical_max_extent",
                                0.0,
                            )
                            or 0.0
                        )
                        if extent > 0:
                            vertical = min(vertical, extent)
                        if vertical <= 0 or not is_attached(target):
                            break
                        self._last_restore_pixels = None
                        try:
                            await target.scroll_to(
                                offset=vertical,
                                duration=0,
                            )
                        except Exception:
                            pass
                        await asyncio.sleep(0.12)
                        pixels = self._last_restore_pixels
                        if (
                            pixels is not None
                            and pixels < vertical - 2
                        ):
                            # 被内容边界钳制，说明已到底，接受实际位置。
                            self.state.vertical_offset = max(
                                0.0, pixels
                            )
                            break
                        if generation != self._scroll_generation:
                            break

                if generation == self._scroll_generation:
                    break
        finally:
            self._scroll_future = None
            self._restoring_scroll = False

    def _go_to_page(self, event: ft.ControlEvent) -> None:
        # 翻页从新页顶部开始，避免旧页越界偏移。
        self.state.vertical_offset = 0.0
        super()._go_to_page(event)

    def _change_page(self, offset: int) -> None:
        self.state.vertical_offset = 0.0
        super()._change_page(offset)

    def _set_current_page(self, page_index: int) -> None:
        self.state.vertical_offset = 0.0
        super()._set_current_page(page_index)

    def _set_page_size(self, event: ft.ControlEvent) -> None:
        self.state.vertical_offset = 0.0
        super()._set_page_size(event)

    def _record_vertical_offset(
        self,
        event: ft.OnScrollEvent,
        owner: str = "page",
    ) -> None:
        """记录实际滚动的容器，恢复时按 owner 选择目标。"""
        if self._restoring_scroll:
            # 恢复期间仍记录实际像素，用于判断是否被边界钳制。
            try:
                self._last_restore_pixels = max(
                    0.0, float(event.pixels)
                )
            except (TypeError, ValueError):
                self._last_restore_pixels = None
            return
        self.state.vertical_offset = max(
            0.0, float(event.pixels)
        )
        self.state.vertical_owner = owner
        extent = getattr(event, "max_scroll_extent", None)
        if isinstance(extent, (int, float)) and extent >= 0:
            self.state.vertical_max_extent = float(extent)

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
                staff_display(record)
                if self.sort_column == "staff"
                else str(record.get(self.sort_column, ""))
            ),
            reverse=not self.sort_ascending,
        )

    def _display_records(
        self,
        *,
        filtered: bool = True,
    ) -> list[Record]:
        # 合并同一部番功能已移除，直接返回排序后的记录。
        return self._sorted_records(filtered=filtered)

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
                start_x = float(
                    sum(
                        widths[key] + 4
                        for key in keys[:index]
                    )
                )
                end_x = start_x + float(widths[column_key])
                viewport = max(
                    0.0,
                    float((self.page.width or 900) - 48),
                )
                current = max(
                    0.0,
                    float(self.state.horizontal_offset or 0.0),
                )
                max_extent = max(
                    0.0,
                    float(
                        getattr(
                            self.state,
                            "horizontal_max_extent",
                            0.0,
                        )
                        or 0.0
                    ),
                )
                if (
                    start_x >= current
                    and end_x <= current + viewport
                ):
                    # 命中列已经完整可见：保持横向位置不动。
                    target = current
                else:
                    # 只滚动到刚好露出这一列，不居中也不过界。
                    if start_x < current:
                        target = start_x - 40.0
                    else:
                        target = end_x - viewport + 40.0
                    target = max(0.0, target)
                    if max_extent > 0:
                        target = min(target, max_extent)
                if abs(target - current) > 1.0:
                    await self.table_scroll.scroll_to(
                        offset=target,
                        duration=0,
                    )
            row = record_index % self.page_size
            heights = self._last_row_heights
            row_h = (
                heights[row]
                if 0 <= row < len(heights)
                else DATA_ROW_HEIGHT
            )
            # 表头 44px + 行偏移；命中行约落在视口 1/3 处。
            y = 44.0 + row * row_h
            body = self.body
            body_scrollable = (
                getattr(body, "scroll", None) is not None
            )
            target = body if body_scrollable else self.table_body
            if target is None:
                target = body
            viewport = float(
                getattr(target, "height", None)
                or float(self.page.height or 800) - 200
            )
            offset = max(0.0, y - viewport * 0.3)
            # 两次尝试：刚重建时可能被钳到 0。
            for attempt in range(2):
                if getattr(target, "page", None) is not None:
                    try:
                        await target.scroll_to(
                            offset=offset,
                            duration=0,
                        )
                    except Exception:
                        pass
                if attempt == 0:
                    await asyncio.sleep(0.05)
        except Exception:
            pass

    def _sort_by(self, key: str) -> None:
        if self.sort_column == key:
            self.preferences.sort_ascending = not self.sort_ascending
        else:
            self.preferences.sort_column = key
            self.preferences.sort_ascending = False
        self.preferences.save()
        old_extent = getattr(self, "_last_h_extent", 0.0)
        self._restore_ratio = (
            max(0.0, self.state.horizontal_offset) / old_extent
            if old_extent > 0
            else 0.0
        )
        if self.search_query:
            self._resync_search(reset_scroll=False)
        else:
            self.current_page = 0
            self.state.vertical_offset = 0.0
            self.refresh(restore_scroll=True)

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
                for key, label in WATCHED_COLUMNS
                if key != "number"
            ]
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
                False,
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


    # ===== 新布局：卡片与工具栏 =====

    def _card(self, content: ft.Control, *, padding: int = 12) -> ft.Container:
        """统一的白色卡片容器。"""
        return ft.Container(
            bgcolor=self._ui_colors["card_bg"],
            border=ft.Border.all(1, self._ui_colors["border"]),
            border_radius=12,
            padding=padding,
            content=content,
        )

    def _chip(
        self,
        text: str,
        *,
        active: bool,
        on_click,
    ) -> ft.Control:
        """筛选 chip：默认只显示「全部」。"""
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=999,
            bgcolor=self._ui_colors["chip_bg"] if active else self._ui_colors["card_bg"],
            border=ft.Border.all(1, self._ui_colors["border"]),
            on_click=on_click,
            content=ui_text(text, size=12, color=self._ui_colors["chip_fg"]),
        )

    def _toolbar_card(self) -> ft.Control:
        """搜索 + 筛选 chips + 筛选/显示按钮。"""
        chips: list[ft.Control] = []
        if not self._applied_filters:
            chips.append(
                self._chip("全部", active=True, on_click=None)
            )
        else:
            chips.append(
                self._chip(
                    "全部",
                    active=False,
                    on_click=self._clear_filters,
                )
            )
            for mode, value in self._applied_filters:
                label = _FILTER_LABELS.get(mode, mode)
                chips.append(
                    self._chip(
                        f"{label}：{value}",
                        active=True,
                        on_click=self._open_filter_dialog,
                    )
                )
        actions = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    controls=chips,
                ),
                ft.TextButton(
                    content=ui_text("筛选"),
                    on_click=self._open_filter_dialog,
                ),
                ft.TextButton(
                    content=ui_text("显示"),
                    on_click=self._open_display_dialog,
                ),
            ],
        )
        return self._card(
            ft.Column(
                spacing=10,
                controls=[self.search_row, actions],
            )
        )

    def _open_filter_dialog(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        """筛选弹层：复用原有筛选控件。"""
        dialog = ft.AlertDialog(
            modal=True,
            title=ui_text("筛选"),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[self._filter_section()],
                ),
            ),
            actions=[
                ft.TextButton(
                    content=ui_text("关闭"),
                    on_click=lambda e: self.page.pop_dialog(),
                )
            ],
        )
        self.page.show_dialog(dialog)

    def _page_jump_row(self) -> ft.Control:
        """显示弹窗中的页码跳转行。"""
        pages = self._total_pages()
        field = ft.TextField(
            value=str(self.current_page + 1),
            width=48,
            height=30,
            text_size=13,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(
                horizontal=4,
                vertical=0,
            ),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
        )

        def commit(event=None) -> None:
            text = str(field.value or "").strip()
            if not text.isdigit():
                field.value = str(self.current_page + 1)
                try:
                    field.update()
                except Exception:
                    pass
                return
            target = int(text)
            target = max(1, min(pages, target))
            if target - 1 != self.current_page:
                self._set_current_page(target - 1)
            field.value = str(self.current_page + 1)
            try:
                field.update()
            except Exception:
                pass

        field.on_submit = commit
        field.on_blur = commit
        self._commit_page_jump = commit
        return ft.Row(
            spacing=6,
            alignment=(
                ft.MainAxisAlignment.CENTER
                if is_compact_layout(self.page)
                else ft.MainAxisAlignment.START
            ),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ui_text("当前显示", size=13),
                field,
                ui_text("页", size=13),
            ],
        )

    def _open_display_dialog(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        """显示弹层：合并 / 高亮 / 列可见性 / 每页条数 / 页码跳转。"""
        dialog = ft.AlertDialog(
            modal=True,
            title=ui_text("显示"),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        self._options_row(),
                        self._page_size_row(),
                        self._page_jump_row(),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(
                    content=ui_text("关闭"),
                    on_click=self._close_display_dialog,
                )
            ],
        )
        self.page.show_dialog(dialog)

    def _close_display_dialog(self, event=None) -> None:
        """关闭前先提交页码跳转输入。"""
        commit = getattr(self, "_commit_page_jump", None)
        if callable(commit):
            commit(event)
        self.page.pop_dialog()

    def _open_batch_dialog(self) -> None:
        """延迟导入，避免 service 与 views.watchlist 的循环引用。"""
        from bangumi.views.watched.batch_import import (
            open_batch_import_dialog,
        )

        open_batch_import_dialog(self.page, self._on_batch_titles)

    def _on_batch_titles(self, titles: list[str]) -> None:
        """按前缀分组后打开可编辑结果弹窗。"""
        from bangumi.data.anime_grouping import group_anime_titles
        from bangumi.views.watched.batch_import import (
            open_batch_result_dialog,
        )

        anime = group_anime_titles(titles)
        open_batch_result_dialog(
            self.page,
            anime,
            self._import_batch_rows,
        )

    def _import_batch_rows(
        self,
        rows: list[tuple[str, str]],
    ) -> None:
        """把确认后的 (条目, 动画) 写入已阅表格。"""
        from bangumi.data.watched_data import RECORD_FIELDS

        for entry, anime in rows:
            record = {field: "" for field in RECORD_FIELDS}
            record["entry"] = entry
            record["anime"] = anime
            self.records.append(record)
        save_records(self.records)
        self.table_exists = True
        self.current_page = max(0, self._total_pages() - 1)
        self.state.current_page = self.current_page
        self.refresh(reset_scroll=True, update_header=True)
        show_toast(
            self.page,
            f"成功导入 {len({entry for entry, _ in rows})} 条，"
            f"共 {len(rows)} 部动画",
        )

    def _defer(self, action) -> None:
        """延迟一帧再执行，避免菜单关闭时把弹窗一起关掉。"""
        async def run() -> None:
            await asyncio.sleep(0.1)
            try:
                action()
            except Exception:
                pass

        self.page.run_task(run)

    def _more_menu(self) -> ft.PopupMenuButton:
        """右上角「…」菜单：空表时只保留导入等必要项。"""
        items: list[ft.Control] = []
        if self.table_exists:
            items.extend(
                [
                    ft.PopupMenuItem(
                        content=ui_text("导出"),
                        on_click=self._export_table,
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("全修"),
                        on_click=lambda e: self._defer(
                            lambda: self._open_delete_confirmation(
                                None
                            )
                        ),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("使用说明"),
                        on_click=lambda e: open_help(self.page),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("批量导入"),
                        on_click=lambda e: self._defer(
                            self._open_batch_dialog
                        ),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("从 Bangumi 填充"),
                        on_click=lambda e: self._defer(
                            lambda: self._open_fill_dialog(None)
                        ),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("排序：规格"),
                        on_click=lambda e: self._sort_by(
                            "specification"
                        ),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("排序：放送"),
                        on_click=lambda e: self._sort_by(
                            "broadcast"
                        ),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("排序：评分"),
                        on_click=lambda e: self._sort_by("rating"),
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("排序：补完"),
                        on_click=lambda e: self._sort_by(
                            "completion"
                        ),
                    ),
                ]
            )
        else:
            items.extend(
                [
                    ft.PopupMenuItem(
                        content=ui_text("导入"),
                        on_click=self._import_table,
                    ),
                    ft.PopupMenuItem(
                        content=ui_text("使用说明"),
                        on_click=lambda e: open_help(self.page),
                    ),
                ]
            )
        return ft.PopupMenuButton(
            content=ft.Container(
                tooltip="显示菜单",
                content=ft.Icon(
                    ft.Icons.MORE_HORIZ, color=self._ui_colors["text"]
                ),
            ),
            items=items,
        )

    def _reset_all(self, event=None) -> None:
        """重置：清空搜索/筛选/排序，回到第一页并滚到顶部。"""
        self.search_query = ""
        if self.search_field is not None:
            self.search_field.value = ""
        self._search_input_token = (
            getattr(self, "_search_input_token", 0) + 1
        )
        self.filters = []
        self._applied_filters = []
        self.preferences.sort_column = ""
        self.preferences.sort_ascending = False
        self.preferences.save()
        self.current_page = 0
        self.state.current_page = 0
        self.state.vertical_offset = 0.0
        self._recompute_search()
        self.refresh(reset_scroll=True, update_header=True)
        self.page.run_task(self._scroll_body_to, 0.0)

    def _appbar_actions(self) -> list[ft.Control]:
        """AppBar 右侧动作按钮；导出只在「…」菜单里。"""
        if is_mobile(self.page):
            return [
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip="追加",
                    on_click=lambda e: self._open_create_entry_form(),
                ),
                ft.Container(width=10),
                self._more_menu(),
            ]
        return [
            ft.Button(
                content=ui_text("+ 追加"),
                style=ft.ButtonStyle(
                    bgcolor="#4F7CB5",
                    color=self._ui_colors["add_fg"],
                ),
                on_click=lambda e: self._open_create_entry_form(),
            ),
            ft.Container(width=12),
            self._more_menu(),
        ]

    # ===== 表体：固定表头 + 封面行 =====

    _FALLBACK_COVER = "/pic/cover.jpg"

    def _cover_src(self, record: Record) -> str:
        """封面路径；进程内按记录缓存，缺失回退到默认图。"""
        key = str(record.get("uid") or record.get("id") or id(record))
        cache = getattr(self, "_cover_cache", None)
        if cache is None:
            cache = {}
            self._cover_cache = cache
        src = cache.get(key)
        if src is None:
            src = self._FALLBACK_COVER
            try:
                from bangumi.services.bgm_pic import cover_path

                path = cover_path(record.get("id"))
                if path is not None and path.is_file():
                    src = str(path)
            except Exception:
                pass
            cache[key] = src
        return src

    @staticmethod
    def _fmt(value) -> str:
        text = str(value or "").strip()
        return text or "-"

    def _rating_badge(self, rating) -> ft.Control:
        """评分语义色徽章：>=80 绿 / 70-79 蓝 / 60-69 琥珀 / <60 红。"""
        text = str(rating or "").strip()
        if not text:
            return ui_text("-", size=12, color=self._ui_colors["secondary"])
        try:
            score = int(float(text))
        except (TypeError, ValueError):
            return ui_text(text, size=12, color=self._ui_colors["secondary"])
        if score >= 80:
            bg, fg = "#E7F6EC", "#1B7F4B"
        elif score >= 70:
            bg, fg = "#E8F0FB", "#1D4ED8"
        elif score >= 60:
            bg, fg = "#FDF3E3", "#92600A"
        else:
            bg, fg = "#FDEBEB", "#B42318"
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            border_radius=6,
            bgcolor=bg,
            content=ui_text(
                text,
                size=12,
                color=fg,
                weight=ft.FontWeight.BOLD,
            ),
        )

    def _sort_glyph(self, key: str) -> str:
        if self.sort_column != key:
            return ""
        return " ▲" if self.sort_ascending else " ▼"

    def _head_cell(
        self,
        label: str,
        key: str | None = None,
        expand: int = 1,
    ) -> ft.Control:
        """表头单元格；仅排序键可点。"""
        text = ui_text(
            label + (self._sort_glyph(key) if key else ""),
            size=12,
            color=self._ui_colors["secondary"],
            weight=ft.FontWeight.BOLD,
            no_wrap=True,
        )
        return ft.Container(
            expand=expand,
            alignment=ft.Alignment.CENTER_LEFT,
            on_click=(
                (lambda e, k=key: self._sort_by(k))
                if key
                else None
            ),
            content=text,
        )

    def _tag_chip(self, tag: str, record: Record | None = None) -> ft.Control:
        chip = ft.Container(
            bgcolor=self._ui_colors["chip_bg"],
            border_radius=6,
            padding=ft.Padding.symmetric(
                horizontal=int(getattr(self, "_tag_pad_x", 6)),
                vertical=int(getattr(self, "_tag_pad_y", 2)),
            ),
            content=self._hl(
                tag,
                size=int(getattr(self, "_tag_font_size", 11)),
                color=self._ui_colors["chip_fg"],
                column_key="tag",
                record=record,
            ),
        )
        if record is not None:
            chip.on_click = (
                lambda e, r=record, t=tag: open_detail(
                    self.page, self.records, r, TAG, value=t
                )
            )
            chip.on_hover = self._tag_hover
        return chip

    def _tag_hover(self, event: ft.ControlEvent) -> None:
        control = getattr(event, "control", None)
        if control is None:
            return
        control.bgcolor = (
            "#E1E8F2" if is_hover(event) else self._ui_colors["chip_bg"]
        )
        try:
            control.update()
        except Exception:
            pass

    def _row_menu(self, record: Record) -> ft.Container:
        def edit(event) -> None:
            self._open_edit_entry_form(record)

        def delete(event) -> None:
            try:
                index = self.records.index(record)
            except ValueError:
                return
            self._delete_record(index)

        def jump(event) -> None:
            open_detail(self.page, self.records, record, ENTRY)

        def insert_above(event) -> None:
            try:
                index = self.records.index(record)
            except ValueError:
                return
            from bangumi.views.general.entry_form import (
                open_entry_form,
            )

            open_entry_form(
                self.page,
                on_save=lambda new: self._insert_record(index, new),
            )

        holder = ft.Container(
            width=40,
            height=32,
            border_radius=6,
            bgcolor=ft.Colors.TRANSPARENT,
            alignment=ft.Alignment.CENTER,
        )

        def on_hover(event: ft.ControlEvent) -> None:
            dark = self.page.theme_mode == ft.ThemeMode.DARK
            holder.bgcolor = (
                (self._ui_colors["hover_bg"] if dark else "#F0F2F5")
                if is_hover(event)
                else ft.Colors.TRANSPARENT
            )
            try:
                holder.update()
            except Exception:
                pass

        holder.on_hover = on_hover
        holder.content = ft.PopupMenuButton(
            tooltip="显示菜单",
            content=ft.Icon(
                ft.Icons.MORE_HORIZ,
                size=18,
                color=self._ui_colors["secondary"],
            ),
            items=[
                ft.PopupMenuItem(
                    content=ui_text("编辑"),
                    on_click=edit,
                ),
                ft.PopupMenuItem(
                    content=ui_text("删除"),
                    on_click=delete,
                ),
                ft.PopupMenuItem(
                    content=ui_text("跳转"),
                    on_click=jump,
                ),
                ft.PopupMenuItem(
                    content=ui_text("在上方插入"),
                    on_click=insert_above,
                ),
            ],
        )
        return holder

    def _sequel_highlight_uids(self) -> set[str]:
        """条目内任意一部 sequel=true 时，取放送最晚的一部标红。"""
        groups: dict[str, list[Record]] = {}
        for record in self.records:
            key = entry_group_key(record) or str(id(record))
            groups.setdefault(key, []).append(record)
        result: set[str] = set()
        for group in groups.values():
            if not any(r.get("sequel") is True for r in group):
                continue
            latest = None
            latest_date = None
            for record in group:
                date = earliest_broadcast_date(
                    str(record.get("broadcast") or "")
                )
                if date is None:
                    continue
                # 日期相同取列表中靠后的一部。
                if latest is None or date >= latest_date:
                    latest = record
                    latest_date = date
            if latest is not None:
                result.add(str(latest.get("uid") or id(latest)))
        return result

    def _completion_click(self, value: str) -> None:
        """补完日期：打开对应月份的补完页。"""
        key = self._completion_month(value)
        if key is not None:
            self._open_completion_month(key)

    def _title_color(self, record: Record) -> str:
        """续作高亮：命中条目的最晚一部用红色标题。"""
        if not self.preferences.highlight_public_sequels:
            return self._ui_colors["text"]
        uid = str(record.get("uid") or id(record))
        if uid in getattr(self, "_seq_uids", set()):
            return "#D93025"
        return self._ui_colors["text"]

    def _active_span(
        self,
        record: Record | None,
        column_key: str | None,
    ) -> tuple[int, int] | None:
        """当前搜索命中的字段区间（仅用于该行该字段的绿底）。"""
        if record is None or not column_key:
            return None
        if not (0 <= self.search_current < len(self.search_results)):
            return None
        index, key, start, end, _ = self.search_results[
            self.search_current
        ]
        if key != column_key:
            return None
        display = getattr(self, "_render_display", None)
        if display is None:
            display = self._display_records()
        self._render_display = display
        if 0 <= index < len(display) and display[index] is record:
            return start, end
        return None

    def _active_match(
        self,
        record: Record | None,
        column_key: str | None,
        displayed: str,
    ) -> tuple[int, int] | None:
        """按「实际显示的文本」重新定位当前命中的区间。"""
        if self._active_span(record, column_key) is None:
            return None
        from bangumi.core.pinyin_search import find_spans

        matches = find_spans(displayed, self.search_query)
        if not matches:
            return None
        occurrence = 0
        if 0 <= self.search_current < len(self.search_results):
            occurrence = self.search_results[self.search_current][4]
        if not 0 <= occurrence < len(matches):
            occurrence = 0
        return matches[occurrence]

    def _hl(
        self,
        text: str,
        *,
        size: int = 12,
        color: str | None = None,
        weight=None,
        column_key: str | None = None,
        record: Record | None = None,
        no_wrap: bool = True,
        max_lines: int | None = None,
    ) -> ft.Control:
        """搜索命中片段高亮：普通黄底，当前命中绿底。"""
        weight = weight or ft.FontWeight.NORMAL
        color = color or self._ui_colors["secondary"]
        base = ui_text_style(size=size, color=color, weight=weight)
        if not getattr(self, "search_query", ""):
            return ui_text(
                text,
                size=size,
                color=color,
                weight=weight,
                no_wrap=no_wrap,
                max_lines=max_lines,
                overflow=(
                    ft.TextOverflow.ELLIPSIS
                    if max_lines is not None
                    else None
                ),
            )
        span = self._active_match(record, column_key, text)
        return ft.Text(
            spans=highlight_spans(
                text,
                self.search_query,
                base_style=base,
                match_style=ui_text_style(
                    size=size,
                    color=color,
                    weight=weight,
                    bgcolor=SEARCH_HIGHLIGHT_BG,
                ),
                active_style=ui_text_style(
                    size=size,
                    color=color,
                    weight=weight,
                    bgcolor=SEARCH_ACTIVE_BG,
                ),
                active_start=span[0] if span else None,
                active_end=span[1] if span else None,
            ),
            no_wrap=no_wrap,
            max_lines=max_lines,
            overflow=(
                ft.TextOverflow.ELLIPSIS
                if max_lines is not None
                else None
            ),
        )

    def _segment(
        self,
        text: str,
        on_click,
        *,
        column_key: str | None = None,
        record: Record | None = None,
        no_wrap: bool = True,
        max_lines: int | None = None,
    ) -> ft.Control:
        """行内独立文字段：有页面则 hover + 点击，否则纯文本。"""
        content = self._hl(
            text,
            size=int(getattr(self, "_meta_font_size", 12)),
            column_key=column_key,
            record=record,
            no_wrap=no_wrap,
            max_lines=max_lines,
        )
        if text == "-" or on_click is None:
            return content
        return hover_link(
            self.page,
            content,
            self._ui_colors["secondary"],
            on_click,
        )

    def _cover_control(
        self,
        record: Record,
        width: float,
        height: float,
    ) -> ft.Control:
        """与照片墙一致：用 processed_cover 生成缩略图并缓存。"""
        data = None
        try:
            bgm_id = record.get("bgm_id")
            if isinstance(bgm_id, int) and bgm_id != -1:
                data = processed_cover(bgm_id, int(width))
        except Exception:
            data = None
        src = data if data is not None else self._FALLBACK_COVER
        holder = ft.Container(
            width=width,
            height=height,
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=self._ui_colors["chip_bg"],
            scale=1.0,
            animate_scale=ft.Animation(
                180, ft.AnimationCurve.EASE_OUT
            ),
            content=ft.Image(
                src=src,
                width=width,
                height=height,
                fit=ft.BoxFit.COVER,
                gapless_playback=True,
            ),
        )

        def on_hover(event: ft.ControlEvent) -> None:
            holder.scale = 1.05 if is_hover(event) else 1.0
            try:
                holder.update()
            except Exception:
                pass

        def on_click(event: ft.ControlEvent) -> None:
            # 预览用原图，避免放大后模糊；小图仍用缩略图。
            from bangumi.services.bgm_pic import cover_path

            bgm_id = record.get("bgm_id")
            path = cover_path(bgm_id) if isinstance(bgm_id, int) else None
            if path is None or not path.is_file():
                return
            try:
                data = path.read_bytes()
                show_image_preview(
                    self.page,
                    data,
                    title="封面图",
                    max_width=max(
                        320.0,
                        min(
                            720.0,
                            float(self.page.width or 1000) - 160.0,
                        ),
                    ),
                )
            except Exception:
                pass

        holder.on_hover = on_hover
        holder.on_click = on_click
        return holder

    def _row_hover(self, event: ft.ControlEvent) -> None:
        control = getattr(event, "control", None)
        if control is None:
            return
        control.bgcolor = self._ui_colors["hover_bg"] if is_hover(event) else None
        try:
            control.update()
        except Exception:
            pass

    def _watched_row(self, record: Record) -> ft.Control:
        """桌面行：封面 + 标题/副标题/TAG + 各列。"""
        title_size = int(getattr(self, "_title_font_size", 14))
        meta_size = int(getattr(self, "_meta_font_size", 12))
        allow_wrap = bool(getattr(self, "_allow_wrap", False))
        wrap_lines = 2 if allow_wrap else 1
        no_wrap_text = not allow_wrap
        title = record_title(record) or str(
            record.get("anime") or record.get("entry") or ""
        ).strip()
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        year = str(date[0]) if date else "-"
        subtitle = (
            f"{year} · {self._fmt(record.get('category'))}"
            f" · {self._fmt(record.get('specification'))}"
            f" · {self._fmt(staff_display(record))}"
        )
        anim_avail = self._anim_avail(self.current_width())
        title_wrap = allow_wrap and (
            float(text_width(title, size=title_size)) > anim_avail
        )
        meta_wrap = (
            float(text_width(subtitle, size=meta_size)) > anim_avail
        )
        title_lines = 2 if title_wrap else 1
        meta_lines = 2 if meta_wrap else 1
        title_nowrap = not title_wrap
        meta_nowrap = not meta_wrap
        tags = [
            self._tag_chip(tag, record)
            for tag in split_tags(record.get("tag"))[:3]
        ]
        rating = str(record.get("rating") or "").strip()
        completion = self._fmt(record.get("completion"))
        show_studio = self.current_width() >= 1100.0
        show_completion = self.current_width() >= 900.0

        cells: list[ft.Control] = [
            ft.Container(
                expand=3,
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        self._cover_control(record, 48, 68),
                        ft.Column(
                            spacing=4,
                            expand=True,
                            controls=[
                                    hover_link(
                                        self.page,
                                        self._hl(
                                            title or "-",
                                            size=title_size,
                                            color=self._title_color(
                                                record
                                            ),
                                            weight=(
                                                ft.FontWeight.BOLD
                                            ),
                                            column_key="anime",
                                            record=record,
                                            no_wrap=title_nowrap,
                                            max_lines=title_lines,
                                        ),
                                        self._title_color(record),
                                    lambda e, r=record: open_detail(
                                        self.page,
                                        self.records,
                                        r,
                                        ENTRY,
                                    ),
                                ),
                                ft.Row(
                                    spacing=0,
                                    wrap=meta_wrap,
                                    run_spacing=0,
                                    controls=[
                                        ui_text(
                                            f"{year} · ",
                                            size=meta_size,
                                            color=self._ui_colors["secondary"],
                                            no_wrap=meta_nowrap,
                                            max_lines=meta_lines,
                                        ),
                                        self._segment(
                                            self._fmt(
                                                record.get("category")
                                            ),
                                            lambda e, r=record: (
                                                open_detail(
                                                    self.page,
                                                    self.records,
                                                    r,
                                                    CATEGORY,
                                                )
                                            ),
                                        ),
                                        ui_text(
                                            " · ",
                                            size=meta_size,
                                            color=self._ui_colors["secondary"],
                                        ),
                                        ui_text(
                                            self._fmt(
                                                record.get(
                                                    "specification"
                                                )
                                            ),
                                            size=meta_size,
                                            color=self._ui_colors["secondary"],
                                            no_wrap=meta_nowrap,
                                            max_lines=meta_lines,
                                        ),
                                        ui_text(
                                            " · ",
                                            size=meta_size,
                                            color=self._ui_colors["secondary"],
                                        ),
                                        self._segment(
                                            self._fmt(
                                                staff_display(record)
                                            ),
                                            lambda e, r=record: (
                                                open_staff_page(
                                                    self.page,
                                                    self.records,
                                                    r,
                                                )
                                            ),
                                            column_key="staff",
                                            record=record,
                                            no_wrap=meta_nowrap,
                                            max_lines=meta_lines,
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=6,
                                    controls=tags,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ]
        if show_studio:
            cells.append(
                ft.Container(
                    expand=2,
                    alignment=ft.Alignment.CENTER_LEFT,
                    content=StudioLink(
                        self.page,
                        self.records,
                        record,
                        text=self._fmt(record.get("studio")),
                        size=meta_size,
                        color=self._ui_colors["secondary"],
                        no_wrap=True,
                        highlight_query=self.search_query,
                        highlight_bg=SEARCH_HIGHLIGHT_BG,
                        active_span=self._active_match(
                            record,
                            "studio",
                            self._fmt(record.get("studio")),
                        ),
                        active_bg=SEARCH_ACTIVE_BG,
                    ),
                )
            )
        cells.append(
            ft.Container(
                width=getattr(self, "_broadcast_col_width", 140.0),
                alignment=ft.Alignment.CENTER_LEFT,
                content=BroadcastLink(
                    self.page,
                    self.records,
                    record,
                    text=display_broadcast(record),
                    size=meta_size,
                    color=self._ui_colors["secondary"],
                    no_wrap=True,
                    highlight_query=self.search_query,
                    highlight_bg=SEARCH_HIGHLIGHT_BG,
                    active_span=self._active_match(
                        record,
                        "broadcast",
                        display_broadcast(record),
                    ),
                    active_bg=SEARCH_ACTIVE_BG,
                ),
            )
        )
        cells.append(
            ft.Container(
                expand=1,
                alignment=ft.Alignment.CENTER_LEFT,
                content=self._rating_badge(rating),
            )
        )
        if show_completion:
            cells.append(
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER_LEFT,
                    content=(
                        hover_link(
                            self.page,
                            ui_text(
                                completion,
                                size=meta_size,
                                color=self._ui_colors["secondary"],
                                no_wrap=True,
                            ),
                            self._ui_colors["secondary"],
                            lambda e, c=completion: (
                                self._completion_click(c)
                            ),
                        )
                        if self._completion_month(completion)
                        else ui_text(
                            completion,
                            size=meta_size,
                            color=self._ui_colors["secondary"],
                            no_wrap=True,
                        )
                    ),
                )
            )
        cells.append(
            ft.Container(
                width=40,
                alignment=ft.Alignment.CENTER,
                content=self._row_menu(record),
            )
        )
        return ft.Container(
            height=int(getattr(self, "_row_height", 86)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border(
                bottom=ft.BorderSide(1, self._ui_colors["border"])
            ),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=cells,
            ),
        )

    def _mobile_row(self, record: Record) -> ft.Control:
        """移动卡片：封面 + 标题/评分 + 元信息 + TAG + 补完。"""
        title_size = int(getattr(self, "_title_font_size", 14))
        meta_size = int(getattr(self, "_meta_font_size", 12))
        allow_wrap = bool(getattr(self, "_allow_wrap", False))
        wrap_lines = 2 if allow_wrap else 1
        no_wrap_text = not allow_wrap
        title = record_title(record) or str(
            record.get("anime") or record.get("entry") or ""
        ).strip()
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        year = str(date[0]) if date else "-"
        meta = (
            f"{year} · {self._fmt(record.get('category'))}"
            f" · {self._fmt(record.get('specification'))}"
        )
        tags = [
            self._tag_chip(tag, record)
            for tag in split_tags(record.get("tag"))[:3]
        ]
        completion = self._fmt(record.get("completion"))
        return ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=self._ui_colors["card_bg"],
            border=ft.Border.all(1, self._ui_colors["border"]),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    self._cover_control(record, 64, 92),
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Container(
                                        expand=True,
                                        content=hover_link(
                                            self.page,
                                            ui_text(
                                                title or "-",
                                                size=title_size,
                                                color=self._title_color(
                                                    record
                                                ),
                                                weight=ft.FontWeight.BOLD,
                                                no_wrap=no_wrap_text,
                                                max_lines=wrap_lines,
                                                overflow=(
                                                    ft.TextOverflow.ELLIPSIS
                                                ),
                                            ),
                                            self._title_color(record),
                                            lambda e, r=record: (
                                                open_detail(
                                                    self.page,
                                                    self.records,
                                                    r,
                                                    ENTRY,
                                                )
                                            ),
                                        ),
                                    ),
                                    self._rating_badge(
                                        record.get("rating")
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=0,
                                wrap=allow_wrap,
                                run_spacing=0,
                                controls=[
                                    ui_text(
                                        f"{year} · ",
                                        size=meta_size,
                                        color=self._ui_colors["secondary"],
                                        no_wrap=no_wrap_text,
                                        max_lines=wrap_lines,
                                    ),
                                    self._segment(
                                        self._fmt(
                                            record.get("category")
                                        ),
                                        lambda e, r=record: open_detail(
                                            self.page,
                                            self.records,
                                            r,
                                            CATEGORY,
                                        ),
                                    ),
                                    ui_text(
                                        " · ",
                                        size=meta_size,
                                        color=self._ui_colors["secondary"],
                                    ),
                                    ui_text(
                                        self._fmt(
                                            record.get(
                                                "specification"
                                            )
                                        ),
                                        size=meta_size,
                                        color=self._ui_colors["secondary"],
                                        no_wrap=no_wrap_text,
                                        max_lines=wrap_lines,
                                    ),
                                    ui_text(
                                        " · ",
                                        size=meta_size,
                                        color=self._ui_colors["secondary"],
                                    ),
                                    self._segment(
                                        self._fmt(
                                            staff_display(record)
                                        ),
                                        lambda e, r=record: (
                                            open_staff_page(
                                                self.page,
                                                self.records,
                                                r,
                                            )
                                        ),
                                        no_wrap=no_wrap_text,
                                        max_lines=wrap_lines,
                                    ),
                                ],
                            ),
                            ft.Row(spacing=6, controls=tags),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ui_text(
                                        "补完",
                                        size=meta_size,
                                        color=self._ui_colors["secondary"],
                                    ),
                                    ui_text(
                                        completion,
                                        size=meta_size,
                                        color=self._ui_colors["secondary"],
                                        no_wrap=True,
                                    ),
                                ],
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                controls=[self._row_menu(record)],
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _calc_font_scale(
        self,
        rows: list[Record],
        width: float,
    ) -> float:
        """按本页所需文字宽度计算全页统一缩放，范围 0.85~1.0。"""
        if not rows:
            self._allow_wrap = False
            return 1.0
        base_title = 14.0
        base_meta = 12.0
        base_tag = 11.0
        if width < 760:
            card_w = max(240.0, width - 48.0)
            avail = card_w - 64.0 - 24.0 - 48.0 - 12.0
        else:
            # 先按当前可见列计算动画列可用宽度。
            content_w = max(280.0, width - 48.0)
            show_studio = width >= 1100.0
            show_completion = width >= 900.0
            count = 3 + int(show_studio) + int(show_completion)
            fixed = 140.0 + 40.0 + 24.0 + 12.0 * (count - 1)
            units = 4.0 + (2.0 if show_studio else 0.0)
            units += 1.0 if show_completion else 0.0
            anim_col = max(160.0, content_w - fixed) * 3.0 / units
            avail = anim_col - 48.0 - 12.0
        avail = max(120.0, avail)

        need_title = 0.0
        need_meta = 0.0
        need_tags = 0.0
        for record in rows:
            title = record_title(record) or str(
                record.get("anime") or record.get("entry") or ""
            ).strip()
            date = earliest_broadcast_date(
                str(record.get("broadcast") or "")
            )
            year = str(date[0]) if date else "-"
            meta = (
                f"{year} · {self._fmt(record.get('category'))}"
                f" · {self._fmt(record.get('specification'))}"
                f" · {self._fmt(staff_display(record))}"
            )
            need_title = max(
                need_title,
                float(text_width(title, size=int(base_title))),
            )
            need_meta = max(
                need_meta,
                float(text_width(meta, size=int(base_meta))),
            )
            tags = split_tags(record.get("tag"))[:3]
            if tags:
                width_sum = sum(
                    float(text_width(tag, size=int(base_tag))) + 12.0
                    for tag in tags
                )
                width_sum += 6.0 * (len(tags) - 1)
                need_tags = max(need_tags, width_sum)
        needed = max(need_title, need_meta, need_tags, 1.0)
        raw = avail / needed
        # 达到字号下限仍放不下时才允许换行。
        self._allow_wrap = raw < 0.85
        return max(0.85, min(1.0, raw))

    def _table_card(self) -> ft.Control:
        """表格卡：固定表头 + 只渲染当前页的 ListView。"""
        display = self._display_records()
        self._seq_uids = self._sequel_highlight_uids()
        start = self.current_page * self.page_size
        rows = display[start : start + self.page_size]
        width = self.current_width()
        scale = self._calc_font_scale(rows, width)
        self._font_scale = scale
        self._title_font_size = max(13, round(14 * scale))
        self._meta_font_size = max(11, round(12 * scale))
        self._tag_font_size = max(11, round(11 * scale))
        self._tag_pad_x = 6
        self._tag_pad_y = 2
        wrap = bool(getattr(self, "_allow_wrap", False))
        text_h = self._title_font_size + self._meta_font_size + 34
        if wrap:
            text_h = (
                self._title_font_size * 2
                + self._meta_font_size * 2
                + 34
            )
        self._row_height = int(
            max(86, 16 + max(68, text_h))
        )
        if width < 760:
            column = ft.Column(
                spacing=10,
                controls=[self._mobile_row(r) for r in rows],
            )
            self.table_body = None
            self._last_row_heights = [160.0] * len(rows)
            return self._card(column, padding=12)
        # 放送列按内容测宽，保证日期区间完整显示。
        broadcast_w = max(
            (
                float(text_width(self._fmt(r.get("broadcast")), size=12))
                for r in rows
            ),
            default=0.0,
        ) + 20.0
        self._broadcast_col_width = broadcast_w
        show_studio = width >= 1100
        show_completion = width >= 900
        header_cells: list[ft.Control] = [
            self._head_cell("动画", expand=3),
        ]
        if show_studio:
            header_cells.append(self._head_cell("制作公司", expand=2))
        header_cells.append(
            ft.Container(
                width=broadcast_w,
                alignment=ft.Alignment.CENTER_LEFT,
                on_click=lambda e: self._sort_by("broadcast"),
                content=ui_text(
                    "放送" + self._sort_glyph("broadcast"),
                    size=12,
                    color=self._ui_colors["secondary"],
                    weight=ft.FontWeight.BOLD,
                    no_wrap=True,
                ),
            )
        )
        header_cells.append(
            self._head_cell("评分", key="rating", expand=1)
        )
        if show_completion:
            header_cells.append(
                self._head_cell("补完", key="completion", expand=1)
            )
        header_cells.append(
            ft.Container(
                width=40,
                alignment=ft.Alignment.CENTER,
                content=hover_icon(
                    self.page,
                    ft.Icons.RESTART_ALT,
                    tooltip="重置",
                    size=18,
                    padding=6,
                    on_click=lambda e: self._reset_all(),
                ),
            )
        )
        header = ft.Container(
            height=44,
            padding=ft.Padding.symmetric(horizontal=12),
            bgcolor=self._ui_colors["head_bg"],
            border=ft.Border(
                bottom=ft.BorderSide(1, self._ui_colors["border"])
            ),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=header_cells,
            ),
        )
        self._row_controls = [self._watched_row(r) for r in rows]
        self._active_row_index = -1
        self._rendered_query = self.search_query
        self._last_hit_current = -1
        if 0 <= self.search_current < len(self.search_results):
            hit = self.search_results[self.search_current][0]
            if start <= hit < start + len(rows):
                self._active_row_index = hit - start
                self._last_hit_current = self.search_current
        list_view = ft.ListView(
            spacing=0,
            height=(
                max(1, len(rows))
                * float(getattr(self, "_row_height", 86))
            ),
            on_scroll=(
                lambda event: self._record_vertical_offset(
                    event, "table"
                )
            ),
            controls=self._row_controls,
        )
        # 先设好 on_scroll，再注册记忆（remember 会链式包裹）。
        scroll_memory.remember(
            self.page, "/watched", "list", list_view
        )
        self.table_body = list_view
        self._last_row_heights = [
            float(getattr(self, "_row_height", 86))
        ] * len(rows)
        return self._card(
            ft.Column(
                spacing=0,
                controls=[header, list_view],
            ),
            padding=0,
        )

    def _pagination_card(self) -> ft.Control:
        return self._card(self._pagination_bar())

    def _page_numbers(self, pages: int) -> list[int | None]:
        """页码窗口：首尾 + 当前页附近，中间用省略号。"""
        if pages <= 7:
            return list(range(pages))
        wanted = {0, pages - 1, self.current_page}
        for delta in (-1, 1):
            value = self.current_page + delta
            if 0 <= value < pages:
                wanted.add(value)
        ordered = sorted(wanted)
        result: list[int | None] = []
        previous: int | None = None
        for value in ordered:
            if previous is not None and value - previous > 1:
                result.append(None)
            result.append(value)
            previous = value
        return result

    def _pagination_bar(self) -> ft.Control:
        """分页栏：窄屏两行，宽屏数字页码。"""
        pages = self._total_pages()
        total = len(self._display_records())
        narrow = float(self.page.width or 1000) < 1100
        last = self.current_page + 1 >= pages
        first = self.current_page <= 0
        if narrow:
            return ft.Column(
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ui_text(
                        f"第 {self.current_page + 1}/{pages} 页",
                        size=12,
                        color=self._ui_colors["secondary"],
                    ),
                    ft.Row(
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.TextButton(
                                content=ui_text("首页", size=12),
                                disabled=first,
                                on_click=lambda e: self._set_current_page(0),
                            ),
                            ft.TextButton(
                                content=ui_text("上一页", size=12),
                                disabled=first,
                                on_click=lambda e: self._change_page(-1),
                            ),
                            ft.TextButton(
                                content=ui_text("下一页", size=12),
                                disabled=last,
                                on_click=lambda e: self._change_page(1),
                            ),
                            ft.TextButton(
                                content=ui_text("尾页", size=12),
                                disabled=last,
                                on_click=lambda e: self._set_current_page(
                                    pages - 1
                                ),
                            ),
                        ],
                    ),
                ],
            )
        numbers: list[ft.Control] = []
        for value in self._page_numbers(pages):
            if value is None:
                numbers.append(
                    ui_text("…", size=12, color=self._ui_colors["secondary"])
                )
                continue
            active = value == self.current_page
            numbers.append(
                ft.TextButton(
                    content=ui_text(
                        str(value + 1),
                        size=12,
                        weight=(
                            ft.FontWeight.BOLD
                            if active
                            else ft.FontWeight.NORMAL
                        ),
                        color=(
                            self._ui_colors["text"]
                            if active
                            else self._ui_colors["chip_fg"]
                        ),
                    ),
                    disabled=active,
                    on_click=(
                        lambda e, p=value: self._set_current_page(p)
                    ),
                )
            )
        middle = ft.Row(
            spacing=4,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.TextButton(
                    content=ui_text("上一页", size=12),
                    disabled=first,
                    on_click=lambda e: self._change_page(-1),
                ),
                *numbers,
                ft.TextButton(
                    content=ui_text("下一页", size=12),
                    disabled=last,
                    on_click=lambda e: self._change_page(1),
                ),
            ],
        )
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[middle],
        )

    def _empty_card(self) -> ft.Control:
        # 空状态：内容区居中、无卡片边框/背景的次级文本。
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ui_text(
                "还没有记录",
                size=13,
                color=self._ui_colors["secondary"],
            ),
        )


def watched_view(page: ft.Page) -> ft.View:
    instance = WatchedPage(page)
    instance._schedule_scroll_restore()

    def rebuild() -> ft.View:
        query = instance.search_query
        new = WatchedPage(page, instance.state)
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

    # 合并而不是整体覆盖，保留 keep_alive / on_shown / on_restore。
    data = (
        dict(instance.view.data)
        if isinstance(instance.view.data, dict)
        else {}
    )
    data["refresh"] = instance.reload
    data["rebuild"] = rebuild
    data["no_compact_rebuild"] = True
    data.setdefault("keep_alive", True)
    data.setdefault(
        "on_shown", instance._on_shown
    )
    data.setdefault(
        "on_restore", instance._schedule_scroll_restore_force
    )
    data.setdefault("on_close", instance._reset_view_state)
    instance.view.data = data
    return instance.view

