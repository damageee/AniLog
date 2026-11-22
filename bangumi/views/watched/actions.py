"""已阅页面 mixin：actions。"""

from __future__ import annotations


import flet as ft

from bangumi.core.storage import table_file
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.feedback import (
    confirmation_dialog,
)
from bangumi.ui.interaction import (
    hover_icon,
)
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.views.widgets.toast import show_toast

from bangumi.views.watched.constants import *

class ActionsMixin:
    def _action_buttons(self) -> ft.Row:
        compact = is_compact_layout(self.page)
        if compact and self.table_exists:
            def cell(
                icon: str,
                tooltip: str,
                on_click,
                *,
                color: str | None = None,
                on_long_press=None,
            ) -> ft.Container:
                icon_control: ft.Control = hover_icon(
                    self.page,
                    icon,
                    tooltip=(
                        ft.Tooltip(
                            message=tooltip,
                            trigger_mode=ft.TooltipTriggerMode.MANUAL,
                        )
                        if on_long_press is not None
                        else tooltip
                    ),
                    on_click=on_click,
                    color=color,
                    size=20,
                    padding=8,
                )
                if on_long_press is not None:
                    icon_control.on_long_press = on_long_press
                return ft.Container(
                    expand=1,
                    height=40,
                    alignment=ft.Alignment.CENTER,
                    content=icon_control,
                )

            return ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    cell(
                        ft.Icons.ADD,
                        "追加",
                        lambda event: self._open_create_entry_form(),
                    ),
                    cell(
                        ft.Icons.IMPORT_EXPORT,
                        "导出",
                        self._export_table,
                    ),
                    cell(
                        ft.Icons.DELETE_OUTLINE,
                        "全修",
                        self._open_delete_confirmation,
                        color=ft.Colors.RED,
                    ),
                    cell(
                        ft.Icons.REFRESH,
                        "重置",
                        self._reset_sort,
                        on_long_press=self._reset_preferences,
                    ),
                ],
            )
        if self.table_exists:
            actions = [
                ft.Button(
                    content=ui_text("追加"),
                    on_click=lambda event: self._open_create_entry_form(),
                ),
                ft.Button(
                    content=ui_text("导出"),
                    on_click=self._export_table,
                ),
                ft.Button(
                    content=ui_text("全修"),
                    on_click=self._open_delete_confirmation,
                ),
                ft.Button(
                    content=ui_text("重置"),
                    on_click=self._reset_sort,
                    on_long_press=self._reset_preferences,
                ),
            ]
        else:
            if compact:
                return ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            expand=1,
                            content=ft.Button(
                                content=ui_text("新建"),
                                height=40,
                                on_click=lambda event: (
                                    self._open_create_entry_form()
                                ),
                            ),
                        ),
                        ft.Container(
                            expand=1,
                            content=ft.Button(
                                content=ui_text("导入"),
                                height=40,
                                on_click=self._import_table,
                            ),
                        ),
                    ],
                )
            actions = [
                ft.Button(
                    content=ui_text("新建"),
                    on_click=lambda event: self._open_create_entry_form(),
                ),
                ft.Button(
                    content=ui_text("导入"),
                    on_click=self._import_table,
                ),
            ]
        return ft.Row(
            controls=actions,
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

    def _reset_sort(self, event: ft.ControlEvent) -> None:
        typed = str(self.search_field.value or "")
        has_sort = bool(self.sort_column)
        has_filters = bool(self.filters)
        has_search = bool(self.search_query) or bool(typed)
        if not has_sort and not has_filters and not has_search:
            return
        if has_sort:
            self.preferences.sort_column = ""
            self.preferences.sort_ascending = False
            self.preferences.save()
        if has_filters:
            self.filters = []
            self._applied_filters = []
            try:
                self._render_filters()
            except Exception:
                pass
        if has_search:
            self._clear_search()
        self.current_page = 0
        self.refresh(reset_scroll=True, update_header=True)

    def _reset_preferences(self, event: ft.ControlEvent) -> None:
        # 该按钮属于观影页，因此保留全局主题。
        self.preferences.reset(keep_theme=True)
        self.filters = []
        self._applied_filters = []
        sync_tag_colors(self.records, self.preferences)
        self.anchor_positions.clear()
        self.current_page = 0
        self.state.current_page = 0
        self.state.horizontal_offset = 0.0
        self.state.vertical_offset = 0.0
        self.preferences.save()
        self._resync_search(reset_scroll=True)

    def _open_delete_confirmation(self, event: ft.ControlEvent) -> None:
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="删除表格",
                message="确定删除表格吗？",
                confirm_label="继续",
                on_confirm=self._continue_delete,
            )
        )

    def _continue_delete(self, event: ft.ControlEvent) -> None:
        self.page.pop_dialog()
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="操作不可逆",
                message="此操作不可逆，仍要删除吗？",
                confirm_label="确认删除",
                on_confirm=self._delete_table,
            )
        )

    def _delete_table(self, event: ft.ControlEvent) -> None:
        self.page.pop_dialog()
        try:
            table_file().unlink(missing_ok=True)
        except OSError:
            pass
        try:
            from bangumi.data import prework

            prework.refresh_from_disk()
        except Exception:
            pass
        self.records.clear()
        try:
            sync_tag_colors(self.records, self.preferences)
        except Exception:
            pass
        self.table_exists = False
        self.current_page = 0
        self.state.current_page = 0
        self.state.horizontal_offset = 0.0
        self.state.vertical_offset = 0.0
        try:
            self._clear_search()
        except Exception:
            pass
        try:
            # 只刷新本页，不操作视图栈/路由。
            self.refresh(reset_scroll=True, update_header=True)
        except Exception:
            # 兜底：即使重建失败也显示空状态。
            try:
                self.body.controls = [self._empty_card()]
                self.page.update()
            except Exception:
                pass
        show_toast(self.page, "表格已删除")

