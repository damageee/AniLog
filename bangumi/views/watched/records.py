"""已阅页面 mixin：records。"""

from __future__ import annotations


import flet as ft

from bangumi.ui.theme import (
    ui_text,
    ui_text_style,
)
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.views.general.entry_form import open_entry_form
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.data.watched_data import (
    Record,
    entry_group_key,
    propagate_sequel,
    save_records,
)
from bangumi.data.watchlist_data import load_watchlist, save_watchlist

from bangumi.views.watched.constants import *
from bangumi.views.watched.matching import (
    normalize_watchlist_name,
    duplicate_watchlist_names,
)

class RecordsMixin:
    def _open_create_entry_form(self) -> None:
        open_entry_form(self.page, on_save=self._append_record)

    def _open_insert_entry_form(self, record: Record) -> None:
        index = next(
            (
                position
                for position, item in enumerate(self.records)
                if item is record
            ),
            None,
        )
        if index is None:
            return
        open_entry_form(
            self.page,
            on_save=(
                lambda inserted: self._insert_record(index, inserted)
            ),
        )

    def _insert_record(self, index: int, record: Record) -> None:
        updated = list(self.records)
        position = max(0, min(index, len(updated)))
        updated.insert(position, record)
        if record.get("sequel") is True:
            propagate_sequel(updated, entry_group_key(record), True)
        save_records(updated)
        self.records = updated
        sync_tag_colors(self.records, self.preferences)
        self.table_exists = True
        self.current_page = max(0, position // max(1, self.page_size))
        if self.search_query:
            self._resync_search(reset_scroll=True, update_header=True)
        else:
            self.refresh(reset_scroll=True, update_header=True)
        self._safe_prompt_watchlist_duplicates(record)

    def _open_edit_entry_form(self, record: Record) -> None:
        index = next(
            (
                position
                for position, item in enumerate(self.records)
                if item is record
            ),
            None,
        )
        if index is None:
            return
        open_entry_form(
            self.page,
            record=record,
            on_save=lambda updated: self._update_record(index, updated),
            on_delete=lambda: self._delete_record(index),
        )

    def _append_record(self, record: Record) -> None:
        updated = [*self.records, record]
        if record.get("sequel") is True:
            propagate_sequel(updated, entry_group_key(record), True)
        save_records(updated)
        self.records = updated
        sync_tag_colors(self.records, self.preferences)
        self.table_exists = True
        self.current_page = max(0, self._total_pages() - 1)
        if self.search_query:
            self._resync_search(reset_scroll=True, update_header=True)
        else:
            self.refresh(reset_scroll=True, update_header=True)
        self._safe_prompt_watchlist_duplicates(record)

    def _update_record(self, index: int, record: Record) -> None:
        old_record = (
            self.records[index]
            if 0 <= index < len(self.records)
            else None
        )
        updated = list(self.records)
        updated[index] = record
        propagate_sequel(
            updated,
            entry_group_key(record),
            bool(record.get("sequel")),
        )
        save_records(updated)
        self.records = updated
        sync_tag_colors(self.records, self.preferences)
        if self.search_query:
            self._resync_search()
        else:
            self.refresh()
        if old_record is not None and self._watchlist_fields_changed(
            old_record,
            record,
        ):
            self._safe_prompt_watchlist_duplicates(record)

    def _watchlist_fields_changed(
        self,
        old_record: Record,
        new_record: Record,
    ) -> bool:
        for field in ("anime", "entry"):
            old_value = normalize_watchlist_name(
                old_record.get(field, "")
            )
            new_value = normalize_watchlist_name(
                new_record.get(field, "")
            )
            if old_value != new_value:
                return True
        return False

    def _safe_prompt_watchlist_duplicates(
        self,
        record: Record,
    ) -> None:
        try:
            self._prompt_watchlist_duplicates(record)
        except Exception:
            pass

    def _prompt_watchlist_duplicates(self, record: Record) -> None:
        high, low = load_watchlist()
        names = [*high, *low]
        matches = duplicate_watchlist_names(record, names)
        if not matches:
            return
        self._duplicate_prompt_queue = matches
        self._advance_duplicate_prompt()

    def _advance_duplicate_prompt(self) -> None:
        if not self._duplicate_prompt_queue:
            return
        name = self._duplicate_prompt_queue.pop(0)
        token = object()
        self._duplicate_prompt_token = token
        foreground = foreground_color(self.page)

        def finish(
            delete: bool,
            *,
            pop: bool = True,
        ) -> None:
            if self._duplicate_prompt_token is not token:
                return
            self._duplicate_prompt_token = None
            if pop:
                try:
                    self.page.pop_dialog()
                except Exception:
                    pass
            if delete:
                self._remove_watchlist_name(name)
            self.page.update()
            self._advance_duplicate_prompt()

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=background_color(self.page),
                title=ui_text(
                    "提示",
                    weight=ft.FontWeight.BOLD,
                    color=foreground,
                ),
                title_text_style=ui_text_style(
                    color=foreground,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ui_text(
                    "",
                    spans=[
                        ft.TextSpan("发现你正在追番"),
                        ft.TextSpan(
                            name,
                            style=ui_text_style(
                                weight=ft.FontWeight.BOLD
                            ),
                        ),
                        ft.TextSpan("，是否从待看里删除？"),
                    ],
                    color=foreground,
                ),
                content_text_style=ui_text_style(color=foreground),
                on_dismiss=lambda event: finish(False, pop=False),
                actions=[
                    ft.Button(
                        content=ui_text("取消"),
                        on_click=lambda event: finish(False),
                    ),
                    ft.Button(
                        content=ui_text("确认"),
                        on_click=lambda event: finish(True),
                    ),
                ],
            )
        )

    def _remove_watchlist_name(self, name: str) -> None:
        high, low = load_watchlist()
        if name in high:
            high.remove(name)
        elif name in low:
            low.remove(name)
        else:
            return
        save_watchlist(high, low)

    def _delete_record(self, index: int) -> None:
        updated = list(self.records)
        del updated[index]
        save_records(updated)
        self.records = updated
        sync_tag_colors(self.records, self.preferences)
        if self.search_query:
            self._resync_search(reset_scroll=True)
        else:
            self.refresh()

