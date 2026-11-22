"""随机页图片详情弹窗。"""

from __future__ import annotations

import asyncio
from datetime import datetime

import flet as ft

from bangumi.data.watchlist_data import load_watchlist, save_watchlist
from bangumi.data.watched_data import load_records, save_records
from bangumi.ui.colors import background_color, foreground_color
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.views.general.entry_form import open_entry_form
from bangumi.views.widgets.toast import show_toast

TO_STATUS = {
    "Finished Airing": "已完结",
    "Currently Airing": "放送中",
    "Not yet aired": "未放送",
}


def _field(value) -> str:
    text = str(value or "").strip()
    return text or "-"


def _format_date(value) -> str:
    if not value:
        return "-"
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).strftime("%Y年%m月%d日")
    except ValueError:
        return "-"


def _row(label: str, value) -> ft.Control:
    return ft.Row(
        wrap=True,
        spacing=4,
        controls=[
            ui_text(
                label,
                size=13,
                weight=ft.FontWeight.BOLD,
            ),
            ui_text(_field(value), size=13),
        ],
    )


def _name(res: dict) -> str:
    name = res.get("title_japanese") or res.get("title_english")
    return _field(name)


def _save_new_record(page: ft.Page, record) -> None:
    records = load_records()
    records.append(record)
    save_records(records)
    show_toast(page, "条目追加成功")


def _add_to_watchlist(page: ft.Page, name: str, half: str) -> None:
    high, low = load_watchlist()
    target = high if half == "high" else low
    if name not in target:
        target.append(name)
        save_watchlist(high, low)
    show_toast(
        page,
        "已加入高优先级追番"
        if half == "high"
        else "已加入低优先级追番",
    )


def open_random_detail(page: ft.Page, res: dict) -> None:
    """展示随机结果的字段与后续动作。"""
    res = res or {}
    fg = foreground_color(page)
    name = _name(res)
    rows = [
        _row("原名", res.get("title_japanese") or res.get("title_english")),
        _row("评分", res.get("score")),
        _row("人气", res.get("members")),
        _row("类型", res.get("type")),
        _row("来源", res.get("source")),
        _row("集数", res.get("episodes")),
        _row(
            "状态",
            TO_STATUS.get(res.get("status"), "-"),
        ),
        _row(
            "放送",
            _format_date((res.get("aired") or {}).get("from")),
        ),
        _row("分级", res.get("rating")),
    ]

    def close_dialog() -> None:
        try:
            page.pop_dialog()
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    def on_think_again(event=None) -> None:
        close_dialog()

    def on_watched(event=None) -> None:
        close_dialog()

        async def after_close() -> None:
            await asyncio.sleep(0.12)
            open_entry_form(
                page,
                title="我已经看过了！",
                prefill_anime=name,
                auto_search=True,
                on_save=lambda record: _save_new_record(
                    page, record
                ),
            )

        page.run_task(after_close)

    def show_priority() -> None:
        priority = ft.AlertDialog(
            modal=True,
            bgcolor=background_color(page),
            title=ui_text(
                "我要看这个！",
                weight=ft.FontWeight.BOLD,
                color=fg,
            ),
            content=ui_text("你要加入哪个优先级的追番列表里？"),
            actions=[],
        )

        def pick(half: str):
            def handler(event=None) -> None:
                close_dialog()
                _add_to_watchlist(page, name, half)

            return handler

        priority.actions = [
            ft.TextButton(
                content=ui_text("高"),
                on_click=pick("high"),
            ),
            ft.TextButton(
                content=ui_text("低"),
                on_click=pick("low"),
            ),
            ft.TextButton(
                content=ui_text("想想算了"),
                on_click=lambda e: close_dialog(),
            ),
        ]
        page.show_dialog(priority)

    def on_follow(event=None) -> None:
        close_dialog()

        async def delayed() -> None:
            await asyncio.sleep(0.12)
            show_priority()

        page.run_task(delayed)

    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=background_color(page),
        title=ui_text(
            "感兴趣吗？",
            weight=ft.FontWeight.BOLD,
            color=fg,
        ),
        content=ft.Column(
            tight=True,
            spacing=6,
            controls=rows,
        ),
        actions=[],
    )
    border_color = (
        "#3A4048"
        if page.theme_mode == ft.ThemeMode.DARK
        else "#D8DEE6"
    )

    def outlined(
        label: str,
        handler,
    ) -> ft.OutlinedButton:
        return ft.OutlinedButton(
            content=ui_text(label),
            on_click=handler,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, border_color),
                padding=ft.Padding.symmetric(
                    horizontal=18, vertical=12
                ),
                text_style=ui_text_style(
                    size=14,
                    color=fg,
                ),
            ),
        )

    dialog.actions = [
        outlined("再想想", on_think_again),
        outlined("看过了", on_watched),
        outlined("去追番", on_follow),
    ]
    page.show_dialog(dialog)
