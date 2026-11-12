"""用于打开详情页的可点击文本链接。"""

from __future__ import annotations

import re

import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover

from bangumi.core.pinyin_search import find_spans
from bangumi.ui.theme import UI_FONT, ui_text
from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import (
    hover_copy,
    hover_link,
)
from bangumi.ui.constants import (
    ANIM_BASE_MS,
    HOVER_SCALE_TAG,
)
from bangumi.views.navigation import (
    AUTHOR,
    BROADCAST,
    CAST,
    CATEGORY,
    DETAIL_FIELDS,
    STUDIO,
    TAG,
    DetailKind,
)
from bangumi.views.navigation import open_detail
from bangumi.data.quarter_core import BROADCAST_DATE_RE, start_date
from bangumi.views.widgets.toast import copy_text
from bangumi.ui.tag_colors import (
    FALLBACK_TAG_COLOR,
    is_valid_color,
    relative_luminance,
)
from bangumi.data.watched_data import (
    AUTHOR_SEPARATOR,
    Record,
    split_authors,
    split_tags,
)


def _field_text(record: Record, kind: DetailKind) -> str:
    field = DETAIL_FIELDS.get(kind)
    if field is None:
        return ""
    return str(record.get(field, "") or "")


def _display_text(value: str) -> str:
    return str(value or "").replace("\n", " ")


def _highlight_bg(dark: bool, active: bool) -> str:
    if active:
        return ft.Colors.with_opacity(
            0.75,
            ft.Colors.ORANGE_700 if dark else ft.Colors.ORANGE,
        )
    return ft.Colors.with_opacity(
        0.45 if dark else 0.35,
        ft.Colors.AMBER_700 if dark else ft.Colors.YELLOW,
    )


def highlight_spans(
    text: str,
    query: str,
    *,
    dark: bool = False,
    offset: int = 0,
    active_start: int | None = None,
    active_end: int | None = None,
    on_click=None,
    base_style: ft.TextStyle | None = None,
    match_style: ft.TextStyle | None = None,
) -> list[ft.TextSpan]:
    """将 ``text`` 拆分为片段，并高亮每个查询匹配项。"""
    if not query:
        return [
            ft.TextSpan(text, style=base_style, on_click=on_click)
        ]

    spans: list[ft.TextSpan] = []
    last = 0
    for start, end in find_spans(text, query):
        if start > last:
            spans.append(
                ft.TextSpan(
                    text[last:start],
                    style=base_style,
                    on_click=on_click,
                )
            )
        active = (
            active_start is not None
            and offset + start == active_start
            and offset + end == active_end
        )
        spans.append(
            ft.TextSpan(
                text[start:end],
                style=(
                    match_style
                    if match_style is not None
                    else ft.TextStyle(
                        bgcolor=_highlight_bg(dark, active),
                    )
                ),
                on_click=on_click,
            )
        )
        last = end
    if last < len(text):
        spans.append(
            ft.TextSpan(
                text[last:],
                style=base_style,
                on_click=on_click,
            )
        )
    return spans


def DetailLink(
    page: ft.Page,
    records: list[Record],
    record: Record,
    kind: DetailKind,
    *,
    font_family: str = UI_FONT,
    text: str | None = None,
    size: int = 14,
    color: str | None = None,
    no_wrap: bool = False,
    button: bool = False,
    weight: ft.FontWeight | None = None,
    highlight_query: str = "",
    highlight_start: int | None = None,
    highlight_end: int | None = None,
    reload_records: bool = True,
) -> ft.Control:
    """为单值字段返回轻量文本链接。"""
    display = _display_text(
        _field_text(record, kind) if text is None else text
    )
    text_color = color or foreground_color(page)
    if not display.strip():
        return ui_text(
            display,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
            weight=weight,
        )

    if highlight_query:
        label = ui_text(
            "",
            spans=highlight_spans(
                display,
                highlight_query,
                dark=page.theme_mode == ft.ThemeMode.DARK,
                active_start=highlight_start,
                active_end=highlight_end,
            ),
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
            weight=weight,
        )
    else:
        label = ui_text(
            display,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
            weight=weight,
        )
    def click(event: ft.ControlEvent) -> None:
        if kind == AUTHOR:
            from bangumi.views.general.detail_author import (
                open_author_page,
            )

            open_author_page(page, records, display)
            return
        if kind == CATEGORY:
            from bangumi.views.general.detail_category import (
                open_category_page,
            )

            open_category_page(page, records, display)
            return
        open_detail(
            page,
            records,
            record,
            kind,
            reload_records=reload_records,
        )

    if button:
        return ft.TextButton(
            content=label,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(
                    horizontal=4,
                    vertical=0,
                ),
            ),
            on_click=click,
        )
    return hover_link(page, label, text_color, click)


def _open_studio_company(
    page: ft.Page,
    records: list[Record],
    company: str,
) -> None:
    """打开共用的制作公司作品页，避免循环导入。"""
    from bangumi.views.statistics import open_studio_page

    open_studio_page(page, records, company)


def _open_author(
    page: ft.Page,
    records: list[Record],
    author: str,
) -> None:
    """打开共用的作者作品页，避免循环导入。"""
    from bangumi.views.general.detail_author import open_author_page

    open_author_page(page, records, author)


def StudioLink(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    font_family: str = UI_FONT,
    text: str | None = None,
    size: int = 14,
    color: str | None = None,
    no_wrap: bool = False,
    highlight_query: str = "",
    highlight_start: int | None = None,
    highlight_end: int | None = None,
) -> ft.Control:
    """返回制作公司文本，使每个非空公司都可点击。"""
    display = _display_text(
        _field_text(record, STUDIO) if text is None else text
    )
    text_color = color or foreground_color(page)
    if not display.strip():
        return ui_text(
            display,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        )

    if not highlight_query:
        pieces: list[ft.Control] = []
        parts = display.split("×")
        for index, part in enumerate(parts):
            if index:
                pieces.append(
                    ui_text(
                        "×",
                        size=size,
                        font_family=font_family,
                        color=text_color,
                        no_wrap=no_wrap,
                    )
                )
            company = part.strip()
            if company:
                pieces.append(
                    hover_link(
                        page,
                        ui_text(
                            part,
                            size=size,
                            font_family=font_family,
                            color=text_color,
                            no_wrap=no_wrap,
                        ),
                        text_color,
                        (
                            lambda event, c=company: (
                                _open_studio_company(
                                    page,
                                    records,
                                    c,
                                )
                            )
                        ),
                    )
                )
            elif part:
                pieces.append(
                    ui_text(
                        part,
                        size=size,
                        font_family=font_family,
                        color=text_color,
                        no_wrap=no_wrap,
                    )
                )
        return ft.Row(
            wrap=True,
            spacing=0,
            run_spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=pieces,
        )

    spans: list[ft.TextSpan] = []
    parts = display.split("×")
    dark = page.theme_mode == ft.ThemeMode.DARK
    offset = 0
    for index, part in enumerate(parts):
        company = part.strip()
        if company:
            spans.extend(
                highlight_spans(
                    part,
                    highlight_query,
                    dark=dark,
                    offset=offset,
                    active_start=highlight_start,
                    active_end=highlight_end,
                    on_click=(
                        lambda event, c=company: (
                            _open_studio_company(
                                page,
                                records,
                                c,
                            )
                        )
                    ),
                )
            )
        elif part:
            spans.extend(
                highlight_spans(
                    part,
                    highlight_query,
                    dark=dark,
                    offset=offset,
                    active_start=highlight_start,
                    active_end=highlight_end,
                )
            )
        offset += len(part)
        if index < len(parts) - 1:
            spans.append(ft.TextSpan("×"))
            offset += 1

    return hover_link(
        page,
        ui_text(
            "",
            spans=spans,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        ),
        text_color,
        None,
    )


def AuthorLink(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    font_family: str = UI_FONT,
    text: str | None = None,
    size: int = 14,
    color: str | None = None,
    no_wrap: bool = False,
    highlight_query: str = "",
    highlight_start: int | None = None,
    highlight_end: int | None = None,
) -> ft.Control:
    """返回作者文本，使每个非空作者都可点击。"""
    display = _display_text(
        _field_text(record, AUTHOR) if text is None else text
    )
    text_color = color or foreground_color(page)
    if not split_authors(display):
        return ui_text(
            display,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        )

    if not highlight_query:
        pieces: list[ft.Control] = []
        parts = [
            part
            for part in re.split(r"[、\r\n]+", display)
            if part.strip()
        ]
        for index, part in enumerate(parts):
            author = part.strip()
            if index:
                pieces.append(
                    ui_text(
                        AUTHOR_SEPARATOR,
                        size=size,
                        font_family=font_family,
                        color=text_color,
                        no_wrap=no_wrap,
                    )
                )
            pieces.append(
                hover_link(
                    page,
                    ui_text(
                        part,
                        size=size,
                        font_family=font_family,
                        color=text_color,
                        no_wrap=no_wrap,
                    ),
                    text_color,
                    (
                        lambda event, n=author: _open_author(
                            page,
                            records,
                            n,
                        )
                    ),
                )
            )
        return ft.Row(
            wrap=True,
            spacing=0,
            run_spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=pieces,
        )

    spans: list[ft.TextSpan] = []
    parts = [
        part
        for part in re.split(r"[、\r\n]+", display)
        if part.strip()
    ]
    dark = page.theme_mode == ft.ThemeMode.DARK
    offset = 0
    for index, part in enumerate(parts):
        author = part.strip()
        spans.extend(
            highlight_spans(
                part,
                highlight_query,
                dark=dark,
                offset=offset,
                active_start=highlight_start,
                active_end=highlight_end,
                on_click=(
                    lambda event, n=author: (
                        _open_author(
                            page,
                            records,
                            n,
                        )
                    )
                ),
            )
        )
        offset += len(part)
        if index < len(parts) - 1:
            spans.append(ft.TextSpan(AUTHOR_SEPARATOR))
            offset += len(AUTHOR_SEPARATOR)

    return hover_link(
        page,
        ui_text(
            "",
            spans=spans,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        ),
        text_color,
        None,
    )


def RoleLine(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    font_family: str = UI_FONT,
    name: str,
    cvs: list[str],
    size: int = 14,
    color: str | None = None,
    no_wrap: bool = False,
    copy_role: bool = False,
    highlight_query: str = "",
) -> ft.Control:
    """返回 ``name(cv1/cv2)``，使每个声优都可点击。"""
    text_color = color or foreground_color(page)
    role_click = None
    if copy_role:
        role_click = lambda event: page.run_task(
            copy_text,
            page,
            name,
            "已复制角色名到剪贴板",
        )

    if not highlight_query:
        pieces: list[ft.Control] = []
        if role_click is None:
            pieces.append(
                ui_text(
                    name,
                    size=size,
                    font_family=font_family,
                    color=text_color,
                    no_wrap=no_wrap,
                )
            )
        else:
            pieces.append(
                hover_copy(
                    page,
                    ui_text(
                        name,
                        size=size,
                        font_family=font_family,
                        color=text_color,
                        no_wrap=no_wrap,
                    ),
                    role_click,
                )
            )
        if cvs:
            pieces.append(
                ui_text(
                    "(",
                    size=size,
                    font_family=font_family,
                    color=text_color,
                    no_wrap=no_wrap,
                )
            )
            for index, cv in enumerate(cvs):
                if index:
                    pieces.append(
                        ui_text(
                            "/",
                            size=size,
                            font_family=font_family,
                            color=text_color,
                            no_wrap=no_wrap,
                        )
                    )
                pieces.append(
                    hover_link(
                        page,
                        ui_text(
                            cv,
                            size=size,
                            font_family=font_family,
                            color=text_color,
                            no_wrap=no_wrap,
                        ),
                        text_color,
                        (
                            lambda event, value=cv: open_detail(
                                page,
                                records,
                                {**record, "cast": value},
                                CAST,
                            )
                        ),
                    )
                )
            pieces.append(
                ui_text(
                    ")",
                    size=size,
                    font_family=font_family,
                    color=text_color,
                    no_wrap=no_wrap,
                )
            )
        return ft.Row(
            wrap=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=pieces,
        )

    spans: list[ft.TextSpan] = [
        ft.TextSpan(name, on_click=role_click),
        ft.TextSpan("("),
    ]
    for index, cv in enumerate(cvs):
        if index:
            spans.append(ft.TextSpan("/"))
        spans.append(
            ft.TextSpan(
                cv,
                on_click=(
                    lambda event, value=cv: open_detail(
                        page,
                        records,
                        {**record, "cast": value},
                        CAST,
                    )
                ),
            )
        )
    spans.append(ft.TextSpan(")"))

    text = ui_text(
        "",
        spans=spans,
        size=size,
        font_family=font_family,
        color=text_color,
        no_wrap=no_wrap,
    )
    if copy_role:
        return hover_copy(page, text, None)
    return text


def TagChip(
    page: ft.Page,
    records: list[Record],
    record: Record,
    tag: str,
    color: str,
    *,
    font_family: str = UI_FONT,
    size: int = 12,
    highlight: int = 0,
) -> ft.Container:
    """返回一个可点击的 TAG 标签。"""
    light = relative_luminance(color) >= 0.5
    text_color = "#1F2933" if light else ft.Colors.WHITE
    if highlight >= 2:
        border = ft.Border.all(3, ft.Colors.DEEP_ORANGE)
    elif highlight == 1:
        border = ft.Border.all(2, ft.Colors.BLUE_700)
    else:
        border = ft.Border.all(
            1,
            ft.Colors.with_opacity(
                0.18,
                ft.Colors.BLACK if light else ft.Colors.WHITE,
            ),
        )

    chip = ft.Container(
        bgcolor=color,
        border=border,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        content=ui_text(
            tag,
            size=size,
            font_family=font_family,
            color=text_color,
        ),
        on_click=(
            lambda event: open_detail(
                page,
                records,
                record,
                TAG,
                value=tag,
            )
        ),
    )
    chip.animate_scale = animation(
        ANIM_BASE_MS, ft.AnimationCurve.EASE_OUT
    )
    chip.scale = 1.0

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        chip.scale = HOVER_SCALE_TAG if hovered else 1.0
        try:
            chip.update()
        except Exception:
            pass

    chip.on_hover = on_hover
    return chip


def TagChips(
    page: ft.Page,
    records: list[Record],
    record: Record,
    tag_colors: dict[str, str],
    *,
    font_family: str = UI_FONT,
    size: int = 12,
    highlight_query: str = "",
    active_tag: str | None = None,
    wrap: bool = True,
    alignment: ft.MainAxisAlignment = ft.MainAxisAlignment.CENTER,
) -> ft.Control:
    """返回某条记录 TAG 单元格的全部标签。"""
    tags = split_tags(record.get("tag", ""))
    if not tags:
        return ui_text("", size=size, font_family=font_family)

    query = str(highlight_query or "").casefold()
    chips: list[ft.Control] = []
    for tag in tags:
        color = tag_colors.get(tag)
        if not is_valid_color(color):
            color = FALLBACK_TAG_COLOR
        level = 0
        if query and find_spans(tag, query):
            level = 1
            if tag == active_tag:
                level = 2
        chips.append(
            TagChip(
                page,
                records,
                record,
                tag,
                str(color),
                font_family=font_family,
                size=size,
                highlight=level,
            )
        )

    return ft.Row(
        wrap=wrap,
        spacing=4,
        run_spacing=4,
        alignment=alignment,
        controls=chips,
    )


def BroadcastLink(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    font_family: str = UI_FONT,
    text: str | None = None,
    size: int = 14,
    color: str | None = None,
    no_wrap: bool = False,
    highlight_query: str = "",
    highlight_start: int | None = None,
    highlight_end: int | None = None,
) -> ft.Control:
    """返回放送文本，使每个独立日期都可点击。"""
    display = _display_text(
        _field_text(record, BROADCAST) if text is None else text
    )
    text_color = color or foreground_color(page)
    if not display.strip():
        return ui_text(
            display,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        )
    dark = page.theme_mode == ft.ThemeMode.DARK

    def highlighted(
        value: str,
        *,
        offset: int = 0,
        on_click=None,
    ) -> ft.Text:
        if highlight_query:
            return ui_text(
                "",
                spans=highlight_spans(
                    value,
                    highlight_query,
                    dark=dark,
                    offset=offset,
                    active_start=highlight_start,
                    active_end=highlight_end,
                    on_click=on_click,
                ),
                size=size,
                font_family=font_family,
                color=text_color,
                no_wrap=no_wrap,
            )
        return ui_text(
            value,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        )

    if "~" in display or "～" in display:
        if start_date(display) is None:
            return highlighted(display)

        def open_period(event: ft.ControlEvent) -> None:
            from bangumi.views.general.detail_broadcast_period import (
                open_broadcast_period_page,
            )

            open_broadcast_period_page(page, records, record)

        return hover_link(
            page,
            highlighted(display),
            text_color,
            open_period,
        )

    matches = list(BROADCAST_DATE_RE.finditer(display))
    if not matches:
        return highlighted(display)

    spans: list[ft.TextSpan] = []
    last = 0
    for match in matches:
        if match.start() > last:
            spans.extend(
                highlight_spans(
                    display[last : match.start()],
                    highlight_query,
                    dark=dark,
                    offset=last,
                    active_start=highlight_start,
                    active_end=highlight_end,
                )
            )
        date_text = match.group(0)
        spans.extend(
            highlight_spans(
                date_text,
                highlight_query,
                dark=dark,
                offset=match.start(),
                active_start=highlight_start,
                active_end=highlight_end,
                on_click=(
                    lambda event, row=record, d=date_text: (
                        open_detail(
                            page,
                            records,
                            row,
                            BROADCAST,
                            value=d,
                        )
                    )
                ),
            )
        )
        last = match.end()
    if last < len(display):
        spans.extend(
            highlight_spans(
                display[last:],
                highlight_query,
                dark=dark,
                offset=last,
                active_start=highlight_start,
                active_end=highlight_end,
            )
        )

    return hover_link(
        page,
        ui_text(
            "",
            spans=spans,
            size=size,
            font_family=font_family,
            color=text_color,
            no_wrap=no_wrap,
        ),
        text_color,
        None,
    )
