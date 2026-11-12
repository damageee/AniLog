"""由观影记录构建的只读条目详情页。"""

from __future__ import annotations

from io import BytesIO

import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover
from PIL import Image as PILImage

from bangumi.services.bgm_pic import cover_path
from bangumi.data.preferences import Preferences
from bangumi.ui.platform import is_compact_layout, is_mobile
from bangumi.ui.theme import ui_text
from bangumi.ui.colors import (
    foreground_color,
    link_hover_color,
)
from bangumi.ui.interaction import (
    hover_zoom,
)
from bangumi.ui.layout import (
    page_padding,
)
from bangumi.views.navigation import AUTHOR, CATEGORY, ENTRY, TAG
from bangumi.views.widgets.image_preview import show_image_preview
from bangumi.views.widgets.links import (
    BroadcastLink,
    DetailLink,
    RoleLine,
    StudioLink,
)
from bangumi.views.navigation import open_detail
from bangumi.data.role_core import parse_roles
from bangumi.data.quarter_core import sort_records_by_broadcast
from bangumi.views.widgets.toast import copyable_title
from bangumi.data.watched_data import (
    Record,
    load_records,
    split_authors,
    split_tags,
)

ENTRY_FALLBACK = "条目"


def entry_key(record: Record) -> str:
    """返回用于将记录归入同一条目的值。"""
    value = record.get("entry") or record.get("anime") or ""
    return str(value).strip() or ENTRY_FALLBACK


def _entry_covers(records: list[Record]) -> list[bytes]:
    covers: list[bytes] = []
    seen: set[int] = set()
    for record in records:
        subject_id = record.get("bgm_id")
        if not isinstance(subject_id, int) or subject_id == -1:
            continue
        if subject_id in seen:
            continue
        path = cover_path(subject_id)
        if path is None or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        seen.add(subject_id)
        covers.append(data)
    return covers


def _image_ratio(data: bytes) -> float:
    try:
        with PILImage.open(BytesIO(data)) as image:
            width, height = image.size
        if width <= 0 or height <= 0:
            return 1.0
        return width / height
    except Exception:
        return 1.0


def group_records(records: list[Record], clicked: Record) -> list[Record]:
    key = entry_key(clicked)
    matches = [record for record in records if entry_key(record) == key]
    return matches or [clicked]


def unique_values(branches: list[Record], field: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for record in branches:
        value = str(record.get(field, "") or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def unique_authors(branches: list[Record]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for record in branches:
        for name in split_authors(record.get("author")):
            if name not in seen:
                seen.add(name)
                values.append(name)
    return values


def entry_summary(branches: list[Record]) -> tuple[str, str]:
    authors = " / ".join(unique_authors(branches))
    categories = " / ".join(unique_values(branches, "category"))
    first_line = " · ".join(
        part for part in (authors, categories) if part
    )
    tags = " / ".join(unique_values(branches, "tag"))
    return first_line, tags


def merge_role_entries(
    branches: list[Record],
) -> list[tuple[str, list[str]]]:
    merged: dict[str, list[str]] = {}
    for record in branches:
        for name, cvs in parse_roles(
            str(record.get("role", "") or "")
        ):
            if not name:
                continue
            if name not in merged:
                merged[name] = list(cvs)
                continue
            for cv in cvs:
                if cv not in merged[name]:
                    merged[name].append(cv)
    return list(merged.items())


def merge_roles(branches: list[Record]) -> list[str]:
    lines: list[str] = []
    for name, cvs in merge_role_entries(branches):
        lines.append(
            f"{name}({'/'.join(cvs)})"
            if cvs
            else name
        )
    return lines


def build_entry_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    branches = group_records(records, clicked)
    branches = sort_records_by_broadcast(branches)
    covers = _entry_covers(branches)
    preferences = Preferences.load()
    title = entry_key(clicked)
    compact = is_mobile(page) or is_compact_layout(page)
    foreground = foreground_color(page)
    secondary = _with_opacity(
        0.65,
        foreground,
        fallback=(
            ft.Colors.GREY_600
            if page.theme_mode == ft.ThemeMode.LIGHT
            else ft.Colors.GREY_400
        ),
    )
    border_color = _with_opacity(
        0.3,
        foreground,
        fallback=(
            ft.Colors.GREY_400
            if page.theme_mode == ft.ThemeMode.LIGHT
            else ft.Colors.GREY_600
        ),
    )

    controls: list[ft.Control] = [
        _summary_row(page, records, branches, foreground),
        ft.Divider(height=1),
    ]

    if len(branches) > 1:
        controls.append(
            ui_text(
                "分支",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=foreground,
            )
        )

    for index, record in enumerate(branches, start=1):
        controls.append(
            _branch_card(
                record,
                index,
                page,
                records,
                foreground=foreground,
                secondary=secondary,
                border_color=border_color,
                preferences=preferences,
                route=route,
            )
        )

    if any(record.get("sequel") is True for record in branches):
        controls.append(
            ui_text(
                "续作进行中...",
                size=14,
                color=ft.Colors.RED,
            )
        )

    merged = merge_role_entries(branches)
    if merged:
        controls.extend(
            [
                ft.Divider(height=1),
                ui_text(
                    "角色(CV)",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=foreground,
                ),
            ]
        )
        base = branches[0] if branches else clicked
        controls.extend(
            RoleLine(
                page,
                records,
                base,
                name=name,
                cvs=cvs,
                size=14,
                color=foreground,
                copy_role=True,
            )
            for name, cvs in merged
        )

    if preferences.detail_show_remark:
        remark = ""
        for branch in branches:
            value = str(branch.get("remark") or "").strip()
            if value:
                remark = value
                break
        if remark:
            controls.extend(
                [
                    ft.Divider(height=1),
                    ui_text(
                        "备注",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=foreground,
                    ),
                    ui_text(
                        remark,
                        size=14,
                        color=foreground,
                    ),
                ]
            )

    cover_state: dict[str, object] = {"index": 0, "show": None}

    def next_cover(event: ft.ControlEvent) -> None:
        if len(covers) <= 1:
            return
        cover_state["index"] = (
            int(cover_state["index"]) + 1
        ) % len(covers)
        show = cover_state.get("show")
        if callable(show):
            show(int(cover_state["index"]))

    def previous_cover(event: ft.ControlEvent) -> None:
        if len(covers) <= 1:
            return
        cover_state["index"] = (
            int(cover_state["index"]) - 1
        ) % len(covers)
        show = cover_state.get("show")
        if callable(show):
            show(int(cover_state["index"]))

    def open_cover(event: ft.ControlEvent) -> None:
        show_image_preview(
            page,
            covers[cover_state["index"]],
            max_width=min(
                720.0,
                float(page.width or 1000) - 96,
            ),
        )

    def cover_tooltip() -> str:
        return (
            "单击切换封面，长按查看大图"
            if len(covers) > 1
            else "长按查看大图"
        )

    column_controls: list[ft.Control] = controls
    image_container: ft.GestureDetector | None = None
    image_control: ft.Control | None = None
    cover_ratio = 1.0
    cover_pad = 24.0

    def cover_image_control(
        index: int,
        width: float,
        height: float,
        key: str,
    ) -> ft.Image:
        return ft.Image(
            src=covers[index],
            width=width,
            height=height,
            fit=ft.BoxFit.CONTAIN,
            gapless_playback=True,
            key=key,
        )

    def make_cover_switcher(
        width: float,
        height: float,
    ) -> ft.AnimatedSwitcher:
        return ft.AnimatedSwitcher(
            content=cover_image_control(
                0, width, height, "cover-0-0"
            ),
            width=width,
            height=height,
            duration=ft.Duration(milliseconds=220),
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            transition=ft.AnimatedSwitcherTransition.FADE,
            animate_size=animation(
                220, ft.AnimationCurve.EASE_OUT
            ),
        )

    if covers and compact:
        cover_width = max(
            120.0,
            (float(page.width or 1000) - 48) / 2,
        )
        first_ratio = _image_ratio(covers[0]) or 1.0
        cover_height = cover_width / first_ratio
        cover_switcher = make_cover_switcher(
            cover_width, cover_height
        )
        cover_token = {"value": 0}

        def show_cover(index: int) -> None:
            width = max(
                120.0,
                (float(page.width or 1000) - 48) / 2,
            )
            ratio = _image_ratio(covers[index]) or 1.0
            height = width / ratio
            cover_token["value"] += 1
            cover_switcher.width = width
            cover_switcher.height = height
            cover_switcher.content = cover_image_control(
                index,
                width,
                height,
                f"cover-{index}-{cover_token['value']}",
            )
            try:
                cover_switcher.update()
            except Exception:
                pass

        cover_state["show"] = show_cover
        image_control = cover_switcher
        image_container = ft.GestureDetector(
            on_tap=next_cover,
            on_secondary_tap=previous_cover,
            on_long_press=open_cover,
            content=ft.Container(
                tooltip=(
                    None
                    if is_mobile(page)
                    else cover_tooltip()
                ),
                content=cover_switcher,
            ),
        )
        column_controls = [
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[hover_zoom(page, image_container)],
            ),
            ft.Divider(height=1),
            *controls,
        ]
    elif covers:
        cover_ratio = _image_ratio(covers[0])
        page_w = float(page.width or 1000)
        page_h = float(page.height or 800)
        text_need = min(520.0, max(320.0, page_w * 0.45))
        available = page_w - cover_pad * 2 - text_need - 16
        height_by_width = available / cover_ratio
        max_height = page_h * 0.75
        min_height = page_h * 0.25
        image_height = min(max_height, height_by_width)

        if image_height >= min_height:
            cover_width = image_height * cover_ratio
            cover_switcher = make_cover_switcher(
                cover_width, image_height
            )
            cover_token = {"value": 0}

            def show_cover(index: int) -> None:
                width = float(cover_switcher.width or 0)
                height = float(cover_switcher.height or 0)
                cover_token["value"] += 1
                cover_switcher.content = cover_image_control(
                    index,
                    width,
                    height,
                    f"cover-{index}-{cover_token['value']}",
                )
                try:
                    cover_switcher.update()
                except Exception:
                    pass

            cover_state["show"] = show_cover
            image_control = cover_switcher
            image_container = ft.GestureDetector(
                on_tap=next_cover,
                on_secondary_tap=previous_cover,
                on_long_press=open_cover,
                content=ft.Container(
                    tooltip=(
                        None
                        if is_mobile(page)
                        else cover_tooltip()
                    ),
                    content=cover_switcher,
                ),
            )
            column_controls = [
                *controls[:2],
                ft.Container(height=10),
                ft.Row(
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=10,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                            controls=controls[2:],
                        ),
                        hover_zoom(page, image_container),
                    ],
                ),
            ]
        else:
            fallback_height = max(120.0, page_h / 4)
            fallback_width = fallback_height * cover_ratio
            cover_switcher = make_cover_switcher(
                fallback_width, fallback_height
            )
            cover_token = {"value": 0}

            def show_cover(index: int) -> None:
                width = float(cover_switcher.width or 0)
                height = float(cover_switcher.height or 0)
                cover_token["value"] += 1
                cover_switcher.content = cover_image_control(
                    index,
                    width,
                    height,
                    f"cover-{index}-{cover_token['value']}",
                )
                try:
                    cover_switcher.update()
                except Exception:
                    pass

            cover_state["show"] = show_cover
            cover_control = ft.GestureDetector(
                on_tap=next_cover,
                on_secondary_tap=previous_cover,
                on_long_press=open_cover,
                content=ft.Container(
                    tooltip=(
                        None
                        if is_mobile(page)
                        else cover_tooltip()
                    ),
                    content=cover_switcher,
                ),
            )
            controls[0:0] = [
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[hover_zoom(page, cover_control)],
                ),
                ft.Divider(height=1),
            ]

    view = ft.View(
        route=route,
        appbar=ft.AppBar(title=copyable_title(page, title)),
        padding=page_padding(),
        controls=[
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=column_controls,
            ),
        ],
    )
    view.data = {
        "rebuild": lambda: build_entry_view(
            page,
            load_records(),
            clicked,
            route,
        )
    }

    compact_image = compact and image_container is not None

    if image_container is not None and image_control is not None:
        previous_resize = page.on_resize

        def on_resize(event: ft.ControlEvent) -> None:
            if view in page.views and page.views[-1] is view:
                page_w = float(page.width or 1000)
                if compact_image:
                    index = int(cover_state["index"])
                    new_width = max(120.0, (page_w - 48) / 2)
                    ratio = _image_ratio(covers[index]) or 1.0
                    new_height = new_width / ratio
                    if abs(float(image_control.width or 0) - new_width) > 1:
                        image_control.width = new_width
                        image_control.height = new_height
                        child = getattr(image_control, "content", None)
                        if isinstance(child, ft.Image):
                            child.width = new_width
                            child.height = new_height
                        try:
                            image_container.update()
                        except Exception:
                            pass
                else:
                    page_h = float(page.height or 800)
                    text_need = min(
                        520.0,
                        max(320.0, page_w * 0.45),
                    )
                    available = (
                        page_w - cover_pad * 2 - text_need - 16
                    )
                    height_by_width = available / cover_ratio
                    max_height = page_h * 0.75
                    min_height = page_h * 0.25
                    height = min(max_height, height_by_width)
                    if height < min_height:
                        height = min_height
                    new_width = height * cover_ratio
                    if abs(float(image_control.height or 0) - height) > 1:
                        image_control.height = height
                        image_control.width = new_width
                        child = getattr(image_control, "content", None)
                        if isinstance(child, ft.Image):
                            child.height = height
                            child.width = new_width
                        try:
                            image_container.update()
                        except Exception:
                            pass
            if previous_resize is not None:
                previous_resize(event)

        page.on_resize = on_resize

    return view


def _summary_row(
    page: ft.Page,
    records: list[Record],
    branches: list[Record],
    foreground: str,
) -> ft.Control:
    authors = unique_authors(branches)
    categories = unique_values(branches, "category")
    if not authors and not categories:
        return ui_text("", size=18, color=foreground)

    base = branches[0]
    controls: list[ft.Control] = []
    for index, value in enumerate(authors):
        if index:
            controls.append(ui_text(" / ", size=18, color=foreground))
        controls.append(
            DetailLink(
                page,
                records,
                {**base, "author": value},
                AUTHOR,
                text=value,
                size=18,
                color=foreground,
            )
        )

    if authors and categories:
        controls.append(ui_text(" · ", size=18, color=foreground))

    for index, value in enumerate(categories):
        if index:
            controls.append(ui_text(" / ", size=18, color=foreground))
        controls.append(
            DetailLink(
                page,
                records,
                {**base, "category": value},
                CATEGORY,
                text=value,
                size=18,
                color=foreground,
            )
        )

    return ft.Row(
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
        controls=controls,
    )


def _branch_card(
    record: Record,
    index: int,
    page: ft.Page,
    records: list[Record],
    *,
    route: str,
    foreground: str,
    secondary: str,
    border_color: str,
    preferences: Preferences,
) -> ft.Container:
    anime = str(record.get("anime", "") or "").strip()
    specification = str(record.get("specification", "") or "").strip()
    studio = str(record.get("studio", "") or "").strip()
    rating = str(record.get("rating", "") or "").strip()
    broadcast = str(record.get("broadcast", "") or "").strip()
    tags = split_tags(record.get("tag"))

    details: list[ft.Control] = []
    if specification:
        details.append(
            ui_text(specification, size=14, color=secondary)
        )
    if specification and studio:
        details.append(ui_text(" · ", size=14, color=secondary))
    if studio:
        details.append(
            StudioLink(
                page,
                records,
                record,
                text=studio,
                size=14,
                color=secondary,
            )
        )
    if preferences.detail_show_rating and rating:
        if specification or studio:
            details.append(ui_text(" · ", size=14, color=secondary))
        details.append(ui_text(rating, size=14, color=secondary))
    if not details:
        details.append(ui_text("", size=14, color=secondary))

    anime_text = ui_text(
        anime,
        size=16,
        weight=ft.FontWeight.BOLD,
        color=foreground,
    )
    title_link = ft.Container(
        expand=True,
        on_click=(
            lambda event, r=record: _open_branch_title(
                page,
                records,
                r,
            )
        ),
        on_long_press=(
            lambda event, r=record: _edit_branch_record(
                page,
                records,
                r,
                route,
            )
        ),
        content=anime_text,
    )

    def on_title_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        anime_text.color = (
            link_hover_color(page) if hovered else foreground
        )
        try:
            anime_text.update()
        except Exception:
            pass

    title_link.on_hover = on_title_hover

    title_row = ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=8,
        controls=[
            ft.Container(
                width=28,
                content=ui_text(
                    f"{index:02d}",
                    size=14,
                    color=secondary,
                ),
            ),
            title_link,
        ],
    )

    branch_controls: list[ft.Control] = [
        title_row,
        ft.Row(
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            controls=details,
        ),
    ]
    if tags:
        tag_controls: list[ft.Control] = []
        for tag_index, tag in enumerate(tags):
            if tag_index:
                tag_controls.append(
                    ui_text(" / ", size=14, color=secondary)
                )
            tag_text = ui_text(tag, size=14, color=secondary)
            tag_box = ft.Container(
                on_click=lambda event, value=tag: open_detail(
                    page,
                    records,
                    record,
                    TAG,
                    value=value,
                ),
                content=tag_text,
            )

            def on_tag_hover(
                event: ft.ControlEvent,
                text_control=tag_text,
            ) -> None:
                hovered = is_hover(event)
                text_control.color = (
                    link_hover_color(page)
                    if hovered
                    else secondary
                )
                try:
                    text_control.update()
                except Exception:
                    pass

            tag_box.on_hover = on_tag_hover
            tag_controls.append(tag_box)
        branch_controls.append(
            ft.Row(
                wrap=True,
                spacing=0,
                controls=tag_controls,
            )
        )
    branch_controls.append(
        BroadcastLink(
            page,
            records,
            record,
            text=broadcast,
            size=14,
            color=secondary,
        )
    )
    completion = str(record.get("completion", "") or "").strip()
    if preferences.detail_show_completion and completion:
        branch_controls.append(
            ui_text(
                f"鉴赏于{completion}",
                size=14,
                color=secondary,
            )
        )

    return ft.Container(
        border=ft.Border.all(1, border_color),
        border_radius=8,
        padding=14,
        content=ft.Column(
            spacing=4,
            controls=branch_controls,
        ),
    )


def _edit_branch_record(
    page: ft.Page,
    records: list[Record],
    record: Record,
    route: str,
) -> None:
    from bangumi.views.general.entry_form import open_entry_form
    from bangumi.data.watched_data import save_records

    def on_save(updated: Record) -> None:
        for index, item in enumerate(records):
            if item is record:
                records[index] = updated
                break
        save_records(records)
        if len(page.views) >= 2:
            detail = page.views[-2]
            if getattr(detail, "route", "") == route:
                new_view = build_entry_view(
                    page, records, updated, route
                )
                old_appbar = getattr(detail, "appbar", None)
                new_appbar = getattr(new_view, "appbar", None)
                if (
                    old_appbar is not None
                    and new_appbar is not None
                ):
                    old_appbar.title = new_appbar.title
                    old_appbar.actions = new_appbar.actions
                else:
                    detail.appbar = new_appbar
                detail.controls = new_view.controls
                detail.data = new_view.data
                page.update()

    def on_delete() -> None:
        for index, item in enumerate(records):
            if item is record:
                del records[index]
                break
        save_records(records)
        if len(page.views) >= 2:
            detail = page.views[-2]
            if getattr(detail, "route", "") == route:
                page.views.remove(detail)
                page.update()

    open_entry_form(
        page,
        record=record,
        on_save=on_save,
        on_delete=on_delete,
    )


def _open_branch_title(
    page: ft.Page,
    records: list[Record],
    record: Record,
) -> None:
    subject_id = record.get("bgm_id")
    if isinstance(subject_id, int) and subject_id != -1:
        path = cover_path(subject_id)
        if path is not None and path.is_file():
            try:
                data = path.read_bytes()
            except OSError:
                data = b""
            if data:
                show_image_preview(page, data)
                return
    open_detail(page, records, record, ENTRY)


def _with_opacity(
    opacity: float,
    color: str,
    *,
    fallback: str,
) -> str:
    try:
        return ft.Colors.with_opacity(opacity, color)
    except Exception:
        return fallback


def open_entry_page(
    page: ft.Page,
    records: list[Record],
    record: Record,
    *,
    value: str | None = None,
) -> None:
    """打开某条记录的只读条目详情页。"""
    open_detail(page, records, record, ENTRY, value=value)
