"""追季目标页。"""

from __future__ import annotations

import asyncio

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.data.season_data import (
    add_items,
    delete_item,
    delete_quarter,
    get_quarter,
    insert_items,
    move_item,
    set_item_checked,
)
from bangumi.services.season_scraper import fetch_season_titles
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.ui.theme import ui_text
from bangumi.ui.platform import is_compact_layout
from bangumi.ui.interaction import (
    back_icon,
    hover_icon,
)
from bangumi.ui.feedback import (
    confirmation_dialog,
    show_error_dialog,
)
from bangumi.views.navigation import (
    go_back,
    push_view,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.general.entry_form import open_entry_form
from bangumi.data.quarter_core import quarter_label
from bangumi.views.widgets.toast import copy_text, show_toast
from bangumi.views.templates.append_from_text import build_append_from_text_view
from bangumi.data.watched_data import (
    entry_group_key,
    load_records,
    propagate_sequel,
    save_records,
)
from bangumi.views.seasonlist.constants import (
    ACTION_BUTTON_SIZE,
    ACTION_ICON_SIZE,
    ADD_COLOR,
    IMPORT_COLOR,
)
from bangumi.views.seasonlist.utils import (
    hide_loading,
    percent,
    quarter_counts,
    show_loading,
)
from bangumi.views.widgets.progress_bar import (
    build_progress_bar,
    build_stats_row,
)


class SeasonTargetPage:
    """单个季度的目标页：条目、添加与删除操作。"""

    def __init__(
        self,
        page: ft.Page,
        year: int,
        index: int,
        *,
        on_deleted=None,
        on_changed=None,
    ) -> None:
        self.page = page
        self.year = int(year)
        self.index = int(index)
        self.on_deleted = on_deleted
        self.on_changed = on_changed
        self.quarter: dict = {}
        self._importing = False
        self._import_ring = None
        self.import_button: ft.Button | None = None
        self.body = ft.Column(
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[],
        )
        self.view = ft.View(
            route=f"/season/{self.year}/{self.index}",
            appbar=ft.AppBar(
                title=ui_text(
                    f"{quarter_label(self.year, self.index)} —— 目标"
                )
            ),
            padding=page_padding(),
            controls=[vertical_page([self.body], stretch=True)],
        )
        self.view.data = {
            "rebuild": lambda: SeasonTargetPage(
                page,
                year,
                index,
                on_deleted=on_deleted,
                on_changed=on_changed,
            ).view
        }
        self.refresh()

    def refresh(self) -> None:
        self.quarter = get_quarter(self.year, self.index) or {
            "year": self.year,
            "quarter": self.index,
            "items": [],
        }
        items = self.quarter.get("items")
        if not isinstance(items, list):
            items = []
        done, total = quarter_counts(self.quarter)
        self.stats_row = build_stats_row(done, total)
        self.progress_bar = build_progress_bar(
            self.page,
            done,
            total,
        )
        controls: list[ft.Control] = [
            self.stats_row,
            self.progress_bar,
        ]
        for item_index, item in enumerate(items):
            if isinstance(item, dict):
                name = str(item.get("name") or "")
                checked = bool(item.get("checked"))
            else:
                name = str(item)
                checked = False
            if not name.strip():
                continue
            controls.append(
                self._item_row(
                    item_index,
                    name,
                    len(items),
                    checked,
                )
            )
        controls.append(self._add_button())
        controls.append(self._import_button())
        controls.append(self._delete_button())
        self.body.controls = controls

    def _item_row(
        self,
        item_index: int,
        name: str,
        total: int,
        checked: bool,
    ) -> ft.Row:
        checkbox = ft.Checkbox(
            value=checked,
            on_change=(
                lambda event, i=item_index: self._toggle_item(
                    i,
                    bool(event.control.value),
                )
            ),
        )
        name_button = ft.Button(
            content=ui_text(name),
            on_click=None,
            expand=True,
        )
        compact = is_compact_layout(self.page)
        if compact:
            menu = ft.ContextMenu(
                expand=True,
                content=name_button,
                items=self._item_menu_items(item_index, name),
                primary_trigger=None,
                secondary_trigger=None,
                tertiary_trigger=None,
            )
            name_button.on_long_press = (
                lambda event: self.page.run_task(menu.open)
            )
            body: ft.Control = ft.Container(
                expand=True,
                content=menu,
            )
        else:
            actions = ft.Row(
                spacing=0,
                visible=False,
                controls=self._row_actions(
                    item_index,
                    name,
                    total,
                ),
            )
            body = ft.Container(
                expand=True,
                content=ft.GestureDetector(
                    on_enter=(
                        lambda event, row=actions: (
                            self._set_row_actions(row, True)
                        )
                    ),
                    on_exit=(
                        lambda event, row=actions: (
                            self._set_row_actions(row, False)
                        )
                    ),
                    content=ft.Row(
                        spacing=0,
                        controls=[name_button, actions],
                    ),
                ),
            )
        return ft.Row(
            spacing=0,
            controls=[checkbox, body],
        )

    def _row_actions(
        self,
        item_index: int,
        name: str,
        total: int,
    ) -> list[ft.Control]:
        buttons: list[ft.Control] = []
        if item_index > 0:
            buttons.append(
                self._action_icon(
                    ft.Icons.MOVE_UP,
                    "上移",
                    lambda event, i=item_index: (
                        self._move_row_item(i, -1)
                    ),
                )
            )
        if item_index < total - 1:
            buttons.append(
                self._action_icon(
                    ft.Icons.MOVE_DOWN,
                    "下移",
                    lambda event, i=item_index: (
                        self._move_row_item(i, 1)
                    ),
                )
            )
        buttons.extend(
            [
                self._action_icon(
                    ft.Icons.CONTENT_COPY,
                    "复制名称",
                    lambda event, n=name: self.page.run_task(
                        copy_text,
                        self.page,
                        n,
                        "已复制动画名称",
                    ),
                ),
                self._action_icon(
                    ft.Icons.TABLE_CHART,
                    "记录动画",
                    lambda event, n=name: open_entry_form(
                        self.page,
                        record={"anime": n, "entry": n},
                        on_save=self._save_to_watched,
                        prefill_anime=n,
                        auto_search=True,
                    ),
                ),
                self._action_icon(
                    ft.Icons.PLAYLIST_ADD,
                    "在上方插入",
                    lambda event, i=item_index: (
                        self._open_insert(i)
                    ),
                ),
                self._action_icon(
                    ft.Icons.DELETE,
                    "删除动画",
                    lambda event, i=item_index, n=name: (
                        self._request_delete_item(i, n)
                    ),
                    color=ft.Colors.RED,
                ),
            ]
        )
        return buttons

    def _action_icon(
        self,
        icon,
        tooltip: str,
        handler,
        *,
        color: str | None = None,
    ) -> ft.Control:
        return hover_icon(
            self.page,
            icon,
            size=ACTION_ICON_SIZE,
            color=color,
            tooltip=tooltip,
            on_click=handler,
            padding=max(
                0,
                int(
                    (ACTION_BUTTON_SIZE - ACTION_ICON_SIZE)
                    / 2
                ),
            ),
        )

    def _set_row_actions(
        self,
        row: ft.Row,
        visible: bool,
    ) -> None:
        if row.visible == visible:
            return
        row.visible = visible
        try:
            row.update()
        except Exception:
            pass

    def _item_menu_items(
        self,
        item_index: int,
        name: str,
    ) -> list[ft.PopupMenuItem]:
        items = self.quarter.get("items")
        total = len(items) if isinstance(items, list) else 0
        menu_items: list[ft.PopupMenuItem] = []
        if item_index > 0:
            menu_items.append(
                ft.PopupMenuItem(
                    icon=ft.Icons.MOVE_UP,
                    content=ui_text("上移"),
                    on_click=(
                        lambda event, i=item_index: (
                            self._move_row_item(i, -1)
                        )
                    ),
                )
            )
        if item_index < total - 1:
            menu_items.append(
                ft.PopupMenuItem(
                    icon=ft.Icons.MOVE_DOWN,
                    content=ui_text("下移"),
                    on_click=(
                        lambda event, i=item_index: (
                            self._move_row_item(i, 1)
                        )
                    ),
                )
            )
        menu_items.extend(
            [
                ft.PopupMenuItem(
                    icon=ft.Icons.CONTENT_COPY,
                    content=ui_text("复制名称"),
                    on_click=lambda event, n=name: self.page.run_task(
                        copy_text,
                        self.page,
                        n,
                        "已复制动画名称",
                    ),
                ),
                ft.PopupMenuItem(
                    icon=ft.Icons.TABLE_CHART,
                    content=ui_text("记录动画"),
                    on_click=lambda event, n=name: open_entry_form(
                        self.page,
                        record={"anime": n, "entry": n},
                        on_save=self._save_to_watched,
                        prefill_anime=n,
                        auto_search=True,
                    ),
                ),
                ft.PopupMenuItem(
                    icon=ft.Icons.PLAYLIST_ADD,
                    content=ui_text("在上方插入"),
                    on_click=(
                        lambda event, i=item_index: self._open_insert(i)
                    ),
                ),
                ft.PopupMenuItem(
                    icon=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED),
                    content=ui_text("删除动画", color=ft.Colors.RED),
                    on_click=lambda event, i=item_index, n=name: (
                        self._request_delete_item(i, n)
                    ),
                ),
            ]
        )
        return menu_items

    def _move_row_item(
        self,
        item_index: int,
        delta: int,
    ) -> None:
        try:
            moved = move_item(
                self.year,
                self.index,
                item_index,
                delta,
            )
        except Exception as error:
            show_error_dialog(
                self.page,
                title="移动失败",
                message=str(error),
            )
            return
        if moved:
            self.refresh()
            self.page.update()
            self._notify_changed()

    def _notify_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()

    def _toggle_item(
        self,
        item_index: int,
        checked: bool,
    ) -> None:
        try:
            saved = set_item_checked(
                self.year,
                self.index,
                item_index,
                checked,
            )
        except Exception as error:
            show_error_dialog(
                self.page,
                title="保存失败",
                message=str(error),
            )
            self.refresh()
            self.page.update()
            return
        if saved:
            items = self.quarter.get("items")
            if (
                isinstance(items, list)
                and 0 <= item_index < len(items)
                and isinstance(items[item_index], dict)
            ):
                items[item_index]["checked"] = checked
        else:
            self.refresh()
        done, total = quarter_counts(self.quarter)
        percentage = percent(done, total)
        self.stats_row.controls[0].value = f"{done}/{total}"
        self.stats_row.controls[1].value = f"{percentage:.1f}%"
        self.progress_bar.value = percentage / 100
        self.page.update()
        self._notify_changed()

    def _save_to_watched(self, record) -> None:
        records = load_records()
        updated = [*records, record]
        if record.get("sequel") is True:
            propagate_sequel(
                updated,
                entry_group_key(record),
                True,
            )
        save_records(updated)
        sync_tag_colors(updated, Preferences.load())

    def _open_insert(self, before_index: int) -> None:
        add_view = build_append_from_text_view(
            self.page,
            "添加动画",
            on_confirm=lambda text: self._insert_added(
                text,
                before_index,
                add_view,
            ),
            on_cancel=lambda: self._close_add(add_view),
            route=(
                f"/season/{self.year}/{self.index}"
                f"/insert/{before_index}"
            ),
        )
        add_view.appbar.automatically_imply_leading = False
        add_view.appbar.leading = back_icon(
            self.page,
            (
                f"/season/{self.year}/{self.index}"
                f"/insert/{before_index}"
            ),
        )
        push_view(self.page, add_view)

    def _insert_added(
        self,
        text: str,
        before_index: int,
        view: ft.View,
    ) -> None:
        names: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            name = line.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        if not names:
            self._close_add(view)
            return
        try:
            insert_items(
                self.year,
                self.index,
                before_index,
                names,
            )
        except Exception as error:
            show_error_dialog(
                self.page,
                title="插入失败",
                message=str(error),
            )
            return
        self._close_add(view)

    def _request_delete_item(
        self,
        item_index: int,
        name: str,
    ) -> None:
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="删除动画",
                message=f"确定删除{name}吗？",
                confirm_label="删除",
                on_confirm=lambda event: self._confirm_delete_item(
                    item_index
                ),
            )
        )

    def _confirm_delete_item(self, item_index: int) -> None:
        self.page.pop_dialog()
        try:
            deleted = delete_item(
                self.year,
                self.index,
                item_index,
            )
        except Exception as error:
            show_error_dialog(
                self.page,
                title="删除失败",
                message=str(error),
            )
            return
        if deleted:
            self.refresh()
            self._notify_changed()
        self.page.update()

    def _add_button(self) -> ft.Button:
        return ft.Button(
            content=ui_text("添加动画", color=ft.Colors.WHITE),
            bgcolor=ADD_COLOR,
            on_click=self._open_add,
        )

    def _import_button(self) -> ft.Button:
        button = ft.Button(
            content=ui_text("网络导入", color=ft.Colors.WHITE),
            bgcolor=IMPORT_COLOR,
            disabled=self._importing,
            on_click=self._request_import,
        )
        self.import_button = button
        return button

    def _request_import(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        if self._importing:
            return
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="网络导入",
                message="将从長門番堂导入新番列表，是否继续",
                confirm_label="确认",
                on_confirm=self._start_import,
            )
        )

    def _start_import(self, event: ft.ControlEvent) -> None:
        self.page.pop_dialog()
        if self._importing:
            return
        self._importing = True
        if self.import_button is not None:
            self.import_button.disabled = True
            self.import_button.update()
        self._import_ring = show_loading(self.page)
        self.page.run_task(self._run_import)

    async def _run_import(self) -> None:
        added: int | None = None
        ring = self._import_ring
        self._import_ring = None
        try:
            try:
                titles = await asyncio.to_thread(
                    fetch_season_titles,
                    self.year,
                    self.index,
                )
                added = await asyncio.to_thread(
                    add_items,
                    self.year,
                    self.index,
                    titles,
                )
            except Exception:
                added = None
        finally:
            hide_loading(self.page, ring)
        self._importing = False
        visible = self.view in self.page.views
        if visible:
            self.refresh()
            self.page.update()
        self._notify_changed()
        if added is None:
            if visible:
                show_error_dialog(
                    self.page,
                    title="网络导入",
                    message="未能获取新番列表",
                )
            return
        if visible:
            show_toast(self.page, f"已导入 {added} 条新番")

    def _delete_button(self) -> ft.Button:
        return ft.Button(
            content=ui_text("删除季度", color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED,
            on_click=self._request_delete,
        )

    def _open_add(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        add_view = build_append_from_text_view(
            self.page,
            "添加动画",
            on_confirm=lambda text: self._save_added(text, add_view),
            on_cancel=lambda: self._close_add(add_view),
            route=f"/season/{self.year}/{self.index}/add",
        )
        add_view.appbar.automatically_imply_leading = False
        add_view.appbar.leading = back_icon(
            self.page,
            f"/season/{self.year}/{self.index}/add",
        )
        push_view(self.page, add_view)

    def _save_added(self, text: str, view: ft.View) -> None:
        names: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            name = line.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        if not names:
            self._close_add(view)
            return
        try:
            add_items(self.year, self.index, names)
        except Exception as error:
            show_error_dialog(
                self.page,
                title="添加失败",
                message=str(error),
            )
            return
        self._close_add(view)

    def _close_add(self, view: ft.View) -> None:
        go_back(self.page, str(getattr(view, "route", "") or ""))
        self.refresh()
        self.page.update()
        self._notify_changed()

    def _request_delete(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="删除季度",
                message=(
                    f"确定删除"
                    f"{quarter_label(self.year, self.index)}吗？"
                ),
                confirm_label="删除",
                on_confirm=self._confirm_delete,
            )
        )

    def _confirm_delete(self, event: ft.ControlEvent) -> None:
        self.page.pop_dialog()
        try:
            delete_quarter(self.year, self.index)
        except Exception as error:
            show_error_dialog(
                self.page,
                title="删除失败",
                message=str(error),
            )
            return
        if self.view in self.page.views:
            go_back(
                self.page,
                str(getattr(self.view, "route", "") or ""),
            )
        if self.on_deleted is not None:
            self.on_deleted()
        self.page.update()
