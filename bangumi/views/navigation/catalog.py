"""顶层页面与详情页维度的目录。

要新增详情维度：
1. 添加 ``DetailKind`` 常量（例如 ``CAST``）。
2. 实现其 builder 并注册到 ``DETAIL_BUILDERS``。
3. 从合适的观影表格单元格通过
   ``open_detail(...)`` 打开它。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

import flet as ft

from bangumi.views.general.detail_author import build_author_view
from bangumi.views.general.detail_broadcast_point import (
    build_broadcast_point_view,
)
from bangumi.views.general.detail_cast import build_cast_view
from bangumi.views.navigation.detail_kinds import (
    AUTHOR,
    BROADCAST,
    CAST,
    CATEGORY,
    ENTRY,
    ROLE,
    QUARTER,
    QUARTER_WORKS,
    REMARK,
    TAG,
    DetailKind,
)
from bangumi.views.general.detail_category import (
    build_category_view,
)
from bangumi.views.general.detail_entry import build_entry_view
from bangumi.views.general.detail_role import (
    build_role_view,
)
from bangumi.views.general.detail_quarter_works import (
    build_quarter_works_view,
)
from bangumi.views.general.detail_remark import build_remark_view
from bangumi.views.general.detail_tag import build_tag_view
from bangumi.data.watched_data import Record


class PageCategory(str, Enum):
    SECTION = "section"
    DETAIL = "detail"


@dataclass(frozen=True)
class PageInfo:
    category: PageCategory
    label: str
    route: str


SECTION_PAGES: tuple[PageInfo, ...] = (
    PageInfo(PageCategory.SECTION, "Home", "/"),
    PageInfo(PageCategory.SECTION, "已阅", "/watched"),
    PageInfo(PageCategory.SECTION, "已追", "/watchlist"),
    PageInfo(PageCategory.SECTION, "追季", "/season"),
    PageInfo(PageCategory.SECTION, "统计", "/statistics"),
    PageInfo(PageCategory.SECTION, "设置", "/settings"),
)

DETAIL_KINDS: tuple[DetailKind, ...] = (
    ENTRY,
    CATEGORY,
    AUTHOR,
    BROADCAST,
    QUARTER,
    QUARTER_WORKS,
    ROLE,
    CAST,
    REMARK,
    TAG,
)
DETAIL_BY_KEY: dict[str, DetailKind] = {
    kind.key: kind for kind in DETAIL_KINDS
}

DETAIL_PAGES: tuple[PageInfo, ...] = tuple(
    PageInfo(
        PageCategory.DETAIL,
        kind.label,
        f"/watched/detail/{kind.key}",
    )
    for kind in DETAIL_KINDS
)
ALL_PAGES: tuple[PageInfo, ...] = SECTION_PAGES + DETAIL_PAGES

DetailBuilder = Callable[
    [ft.Page, list[Record], Record, str],
    ft.View | None,
]
DETAIL_BUILDERS: dict[str, DetailBuilder] = {
    ENTRY.key: build_entry_view,
    CATEGORY.key: build_category_view,
    AUTHOR.key: build_author_view,
    BROADCAST.key: build_broadcast_point_view,
    QUARTER_WORKS.key: build_quarter_works_view,
    ROLE.key: build_role_view,
    CAST.key: build_cast_view,
    REMARK.key: build_remark_view,
    TAG.key: build_tag_view,
}


def build_detail_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    kind: DetailKind,
    route: str,
) -> ft.View | None:
    builder = DETAIL_BUILDERS.get(kind.key)
    if builder is None:
        raise ValueError(f"详情页维度尚未实现: {kind.label}")
    return builder(page, records, clicked, route)
