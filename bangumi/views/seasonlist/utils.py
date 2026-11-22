"""追季页面通用计算与标签辅助。"""

from __future__ import annotations

import datetime as dt

import flet as ft

from bangumi.core.utils import percent


def show_loading(page: ft.Page) -> ft.Container:
    """左下角显示加载转圈。"""
    ring = ft.Container(
        left=24,
        bottom=24,
        width=44,
        height=44,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(
            width=26,
            height=26,
            stroke_width=3,
            color=ft.Colors.BLUE,
        ),
    )
    try:
        page.overlay.append(ring)
        page.update()
    except Exception:
        pass
    return ring


def hide_loading(
    page: ft.Page,
    ring: ft.Container | None,
) -> None:
    """隐藏并移除加载转圈。"""
    if ring is None:
        return
    try:
        if ring in page.overlay:
            page.overlay.remove(ring)
        page.update()
    except Exception:
        pass


def current_year() -> int:
    return dt.date.today().year


def current_season() -> int:
    month = dt.date.today().month
    return (month % 12) // 3


def quarter_counts(quarter: dict) -> tuple[int, int]:
    items = quarter.get("items")
    if not isinstance(items, list):
        return 0, 0
    done = 0
    total = 0
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            total += 1
            if bool(item.get("checked")):
                done += 1
        elif isinstance(item, str) and item.strip():
            total += 1
    return done, total


def apply_label_counts(
    buttons: list[tuple],
    visible: bool,
    page: ft.Page,
) -> None:
    """就地追加或移除现有按钮标签上的数量。"""
    for item in buttons:
        button = item[0]
        label = item[1]
        if len(item) >= 4:
            ok, total = item[2], item[3]
            text = f"{label}({ok}/{total})"
        else:
            text = f"{label}({item[2]})"
        button.content.value = text if visible else label
    if buttons:
        try:
            page.update(*(item[0] for item in buttons))
        except Exception:
            page.update()
