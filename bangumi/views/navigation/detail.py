"""打开详情页并按需加载 catalog。"""

from __future__ import annotations

import flet as ft

from bangumi.data.quarter_core import quarter_target_key
from bangumi.data.watched_data import Record
from bangumi.views.navigation.detail_kinds import (
    DETAIL_FIELDS,
    ENTRY,
    QUARTER,
    QUARTER_WORKS,
    DetailKind,
)
from bangumi.views.navigation.stack import push_view

_DETAIL_SEQUENCE: dict[int, int] = {}
_TARGET_SEPARATOR = "\x00"


def _target_key(
    kind: DetailKind,
    record: Record,
    value: str | None,
) -> str:
    if kind == QUARTER:
        return "quarter:"
    if kind == QUARTER_WORKS:
        return quarter_target_key(
            str(record.get("broadcast", "") or "")
        )
    if kind == ENTRY:
        raw = record.get("entry") or record.get("anime") or ""
    elif value is not None:
        raw = value
    else:
        raw = record.get(DETAIL_FIELDS.get(kind, ""), "")
    return f"{kind.key}{_TARGET_SEPARATOR}{str(raw or '').strip()}"


def open_detail(
    page: ft.Page,
    records: list[Record],
    record: Record,
    kind: DetailKind,
    *,
    value: str | None = None,
    reload_records: bool = True,
) -> None:
    target_key = _target_key(kind, record, value)

    # 点击已打开的条目页分支时，不得再压入
    # 同一详情页的另一个副本。
    if page.views:
        top = page.views[-1]
        top_data = getattr(top, "data", None)
        if (
            getattr(top, "route", "").startswith("/watched/detail/")
            and isinstance(top_data, dict)
            and top_data.get("key") == target_key
        ):
            return

    page_id = id(page)
    sequence = _DETAIL_SEQUENCE.get(page_id, 0) + 1
    _DETAIL_SEQUENCE[page_id] = sequence
    route = f"/watched/detail/{kind.key}/{sequence}"

    field = DETAIL_FIELDS.get(kind)
    if value is not None and field is not None:
        target = {**record, field: value}
    else:
        target = record

    # 在统计/筛选上下文中，调用方的记录可能已经
    # 过滤；条目页必须显示该条目的每个分支。
    if kind == ENTRY and reload_records:
        from bangumi.data.watched_data import load_records

        records = load_records()

    # 延迟导入，使 catalog 能导入 links 而不产生循环。
    from bangumi.views.navigation.catalog import build_detail_view

    view = build_detail_view(page, records, target, kind, route)
    if view is None:
        from bangumi.views.widgets.toast import show_toast

        show_toast(page, "无法解析放送日期")
        return
    data = view.data if isinstance(view.data, dict) else {}
    data["key"] = target_key
    view.data = data
    push_view(page, view)
