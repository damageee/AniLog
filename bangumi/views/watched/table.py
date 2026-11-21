"""已阅页面 mixin：table。"""

from __future__ import annotations

import math

import flet as ft

from bangumi.ui.text_metrics import text_width, truncate_display
from bangumi.ui.platform import is_compact_layout, is_mobile
from bangumi.views.general.detail_role import first_role_name
from bangumi.data.watched_data import (
    Record,
    record_title,
    staff_display,
    split_tags,
)
from bangumi.data.ratings import parse_rating
from bangumi.data.quarter_core import sort_records_by_broadcast
from bangumi.views.templates.list_page import (
    build_list_view,
    open_list_page,
)

from bangumi.views.watched.constants import *

class TableMixin:
    def _table_body_height(self) -> float:
        page_height = float(self.page.height or 800)
        view = self.page.views[-1] if self.page.views else None
        appbar = getattr(view, "appbar", None)
        appbar_h = float(
            getattr(appbar, "toolbar_height", None) or 56.0
        )
        compact = is_compact_layout(self.page)

        # 页面上下 padding 32
        # 固定 header：操作栏 40 + 间距 10 + 搜索栏 40
        # 横向滚动条约 14；表头行 48；表体与分页间距 5
        # 移动端分页在外层：桌面单行 48；紧凑布局 4 行约 184
        if is_mobile(self.page):
            reserve = (
                32.0
                + 90.0
                + 14.0
                + 48.0
                + 5.0
                + (184.0 if compact else 48.0)
                + 12.0
            )
        else:
            reserve = 32.0 + 90.0 + 14.0 + 48.0 + 8.0
        return max(
            MIN_TABLE_BODY_HEIGHT,
            page_height - appbar_h - reserve,
        )

    def _rating_list_entries(
        self,
        score: int,
    ) -> tuple[list[tuple[str, Record]], list[Record]]:
        """筛选评分为 score 的作品，按放送日期从旧到新。"""
        matched = [
            record
            for record in self.records
            if parse_rating(record.get("rating")) == score
        ]
        ordered = sort_records_by_broadcast(matched)
        entries: list[tuple[str, Record]] = []
        seen: dict[str, int] = {}
        for record in ordered:
            text = record_title(record)
            if not text:
                continue
            count = seen.get(text, 0) + 1
            seen[text] = count
            if count > 1:
                text = f"{text} #{count}"
            entries.append((text, record))
        return entries, self.records

    def _open_rating_list(self, score_text: str) -> None:
        """打开所有评分为该分数的作品列表。"""
        score = parse_rating(score_text)
        if score is None:
            return
        title = f"评分（{score}）"
        route = f"/watched/rating/{score}"
        entries, records = self._rating_list_entries(score)

        def rebuild() -> ft.View:
            fresh_entries, fresh_records = self._rating_list_entries(
                score
            )
            return build_list_view(
                self.page,
                title=title,
                route=route,
                entries=fresh_entries,
                records=fresh_records,
                rebuild=rebuild,
            )

        open_list_page(
            self.page,
            title=title,
            route=route,
            entries=entries,
            records=records,
            rebuild=rebuild,
        )

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
                value = (
                    staff_display(record)
                    if key == "staff"
                    else str(record.get(key, ""))
                )
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

