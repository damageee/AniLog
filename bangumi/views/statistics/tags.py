"""标签统计页。"""

from __future__ import annotations

import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover
from bangumi.ui.text_metrics import (
    text_width,
)
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.interaction import FloatingLabel
from bangumi.ui.platform import is_mobile
from bangumi.ui.colors import (
    foreground_color,
    link_hover_color,
)
from bangumi.ui.layout import (
    page_padding,
    scroll_page,
    vertical_page,
)
from bangumi.ui.layout import chart_width as fit_chart_width
from bangumi.ui import scroll_memory
from bangumi.ui.anim import (
    animation,
    entry_animations_enabled,
    wait_until_ready,
)
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.data.watched_data import (
    Record,
    load_records,
)
from bangumi.data.statistics.tags import (
    filtered_anime_items,
    tag_statistics,
)
from bangumi.views.templates.list_page import open_entry_with_back
from bangumi.views.statistics.common.overlays import (
    _OverlayLayers,
    _hide_page_overlay,
    _install_overlay_hook,
    _register_overlay,
)
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    TAG_BAR_HEIGHT,
    TAG_DISPLAY_HEAD,
    TAG_DISPLAY_LIMIT,
    TAG_ROW_SPACING,
    _accent,
)
from bangumi.ui.constants import (
    HOVER_ROW_OPACITY,
)


_WIDE_RANGES = (
    (0x1100, 0x115F),
    (0x2E80, 0xA4CF),
    (0xAC00, 0xD7A3),
    (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F),
    (0xFF00, 0xFF60),
    (0xFFE0, 0xFFE6),
    (0x1F300, 0x1FAFF),
    (0x20000, 0x3FFFD),
)


def _tag_char_width(char: str) -> int:
    code = ord(char)
    return 2 if any(
        low <= code <= high for low, high in _WIDE_RANGES
    ) else 1


def _clip_tag(value: str) -> str:
    """最多保留 16 个显示单元，长标签以 ``..`` 结尾。"""
    text = str(value or "")
    if sum(_tag_char_width(char) for char in text) <= TAG_DISPLAY_LIMIT:
        return text
    kept: list[str] = []
    used = 0
    for char in text:
        char_width = _tag_char_width(char)
        if used + char_width > TAG_DISPLAY_HEAD:
            break
        kept.append(char)
        used += char_width
    return "".join(kept) + ".."


def _tags_content_size(page: ft.Page) -> tuple[float, float]:
    padding = page_padding()
    vertical = float((padding.top or 0) + (padding.bottom or 0))
    available_width = fit_chart_width(
        page,
        float(page.width or 1000),
        min_width=200.0,
    )
    view = page.views[-1] if page.views else None
    appbar = getattr(view, "appbar", None)
    appbar_h = float(getattr(appbar, "toolbar_height", None) or 56.0)
    available_height = max(
        200.0,
        float(page.height or 700) - appbar_h - vertical,
    )
    return available_width, available_height


def _tags_target_width(page: ft.Page) -> float:
    available_width, available_height = _tags_content_size(page)
    return min(
        available_width,
        max(available_height, available_width / 2),
    )


def tags_view(page: ft.Page) -> ft.View:
    play_animation = entry_animations_enabled() and first_entry(
        page, "/statistics/tags"
    )
    if play_animation:
        mark_seen(page, "/statistics/tags")
    prev_selected: list[str] = []
    if page.views:
        top = page.views[-1]
        if (
            str(getattr(top, "route", "")) == "/statistics/tags"
            and isinstance(getattr(top, "data", None), dict)
        ):
            prev_selected = list(
                top.data.get("tag_filters") or []
            )
    records = load_records()
    counts = tag_statistics(records)
    total = len(records) or 1
    fg = foreground_color(page)
    if not counts:
        view = ft.View(
            route="/statistics/tags",
            appbar=ft.AppBar(title=ui_text("标签")),
            padding=page_padding(),
            controls=[
                vertical_page(
                    [
                        ft.Container(
                            alignment=ft.Alignment.TOP_LEFT,
                            content=ui_text(
                                "试试给你的动画加上一些标签来分类吧",
                                size=17,
                                color=fg,
                            ),
                        )
                    ]
                )
            ],
        )
        view.data = {
            "rebuild": lambda: tags_view(page)
        }
        return view
    accent = _accent(page, "#0D9488", "#2DD4BF")
    overlay = _OverlayLayers(page)
    _register_overlay(page, overlay)
    _install_overlay_hook(page)

    selected: list[str] = list(prev_selected)
    bar_specs: list[tuple[ft.Container, float, float]] = []
    anim_state = {"run": True}
    content_width = {"value": _tags_target_width(page)}

    chart_holder = ft.Column(
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[],
    )
    chips_row = ft.Row(
        wrap=True,
        spacing=6,
        run_spacing=6,
        controls=[],
    )
    names_holder = ft.Column(
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[],
    )
    hint = ui_text(
        "点击标签名可筛选动画",
        size=12,
        color=ft.Colors.with_opacity(0.65, fg),
    )
    filter_block = ft.Column(
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[hint, chips_row, names_holder],
    )
    body = ft.Column(
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[chart_holder, filter_block],
    )

    def chip_control(tag: str) -> ft.Control:
        value = str(tag or "").strip()
        display = _clip_tag(value)
        side_padding = 20.0
        close_width = 17.0
        spacing = 4.0
        limit = float(content_width["value"])
        natural = float(text_width(display, size=12))
        overflowing = natural + side_padding + close_width + spacing > limit

        close = ft.Container(
            width=close_width,
            height=close_width,
            alignment=ft.Alignment.CENTER,
            border_radius=8,
            on_click=lambda event, target=value: remove_tag(target),
            tooltip="移除",
            content=ft.Icon(ft.Icons.CLOSE, size=13, color=fg),
        )
        label = ui_text(
            display,
            size=12,
            color=fg,
            no_wrap=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        if overflowing:
            label.expand = True

        return ft.Container(
            width=limit if overflowing else None,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.10, accent),
            border=ft.Border.all(
                1,
                ft.Colors.with_opacity(0.25, accent),
            ),
            tooltip=value,
            content=ft.Row(
                spacing=spacing,
                tight=not overflowing,
                controls=[label, close],
            ),
        )

    def name_row(name: str, record: Record) -> ft.Control:
        row = ft.Container(
            padding=ft.Padding.symmetric(horizontal=4, vertical=5),
            border_radius=6,
            on_click=lambda event, target=record: open_entry_with_back(
                page,
                records,
                target,
                before=lambda: _hide_page_overlay(page),
            ),
            tooltip="打开条目页",
            content=ui_text(name, size=14, color=fg),
        )

        def on_hover(event: ft.ControlEvent) -> None:
            hovered = is_hover(event)
            row.bgcolor = (
                ft.Colors.with_opacity(
                    HOVER_ROW_OPACITY, fg
                )
                if hovered
                else None
            )
            row.update()

        row.on_hover = on_hover
        return row

    def refresh_filters() -> None:
        chips_row.controls = [chip_control(tag) for tag in selected]
        items = filtered_anime_items(records, selected)
        names_holder.controls = [
            name_row(name, record) for name, record in items
        ]
        try:
            page.update(chips_row, names_holder)
        except Exception:
            pass

    def add_tag(tag: str) -> None:
        value = str(tag or "").strip()
        if not value or value in selected:
            return
        selected.append(value)
        refresh_filters()

    def remove_tag(tag: str) -> None:
        value = str(tag or "").strip()
        if value not in selected:
            return
        selected.remove(value)
        refresh_filters()

    def build_chart(width: float, *, animate: bool) -> ft.Control:
        display_tags = [_clip_tag(tag) for tag, _ in counts]
        label_width = max(
            (text_width(label, size=12) for label in display_tags),
            default=20,
        ) + 10.0
        label_width = min(200.0, max(40.0, float(label_width)))
        count_width = 42.0
        gap = TAG_ROW_SPACING
        bar_width = max(
            60.0,
            width - label_width - count_width - gap * 2,
        )

        axis = ft.Row(
            spacing=0,
            controls=[
                ft.Container(width=label_width + gap),
                ft.Container(
                    width=bar_width,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ui_text(
                                label,
                                size=10,
                                color=ft.Colors.with_opacity(0.7, fg),
                            )
                            for label in (
                                "0",
                                "25",
                                "50",
                                "75",
                                "100%",
                            )
                        ],
                    ),
                ),
                ft.Container(width=gap + count_width),
            ],
        )

        rows: list[ft.Control] = [axis, ft.Container(height=4)]
        bar_specs.clear()
        tag_label = FloatingLabel(page)
        pitch = 20.0
        tag_labels: list[ft.Text] = []
        tag_active: dict[str, int | None] = {"index": None}

        def set_tag_highlight(
            index: int | None,
            on: bool,
        ) -> None:
            if index is None or not 0 <= index < len(tag_labels):
                return
            control = tag_labels[index]
            control.color = link_hover_color(page) if on else fg
            try:
                control.update()
            except Exception:
                pass
        for row_index, ((tag, count), display) in enumerate(
            zip(counts, display_tags)
        ):
            ratio = count / total
            fill = ft.Container(
                width=0 if animate else bar_width * ratio,
                height=TAG_BAR_HEIGHT,
                border_radius=TAG_BAR_HEIGHT / 2,
                bgcolor=accent,
                animate=(
                    animation(
                        int(ANIMATION_SECONDS * 1000),
                        ft.AnimationCurve.EASE_OUT,
                    )
                    if animate
                    else None
                ),
            )
            if animate:
                bar_specs.append((fill, ratio, bar_width))

            label_text = ui_text(
                display,
                size=12,
                color=fg,
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
            tag_labels.append(label_text)
            label = ft.Container(
                width=label_width,
                alignment=ft.Alignment.CENTER_RIGHT,
                on_click=lambda event, value=tag: add_tag(value),
                tooltip=(
                    None
                    if is_mobile(page)
                    else f"筛选：{tag}"
                ),
                content=label_text,
            )

            def show_tag(
                event: ft.ControlEvent,
                value: str = tag,
                row: int = row_index,
            ) -> None:
                set_tag_highlight(tag_active["index"], False)
                set_tag_highlight(row, True)
                tag_active["index"] = row
                tag_label.show(event, f"筛选：{value}")

            def move_tag(
                event: ft.ControlEvent,
                base_index: int = row_index,
            ) -> None:
                offset = getattr(
                    event, "local_offset_from_origin", None
                )
                if offset is None:
                    offset = getattr(event, "offset_from_origin", None)
                if offset is None:
                    return
                dy = float(getattr(offset, "y", 0) or 0)
                target = base_index + int(round(dy / pitch))
                target = max(0, min(len(counts) - 1, target))
                set_tag_highlight(tag_active["index"], False)
                set_tag_highlight(target, True)
                tag_active["index"] = target
                tag_label.show(
                    event,
                    f"筛选：{counts[target][0]}",
                )

            def end_tag(event: ft.ControlEvent) -> None:
                set_tag_highlight(tag_active["index"], False)
                tag_active["index"] = None
                tag_label.hide()

            label_gesture = ft.GestureDetector(
                on_long_press_start=show_tag,
                on_long_press_move_update=move_tag,
                on_long_press_end=end_tag,
                on_long_press_cancel=end_tag,
                content=label,
            )

            def on_label_hover(
                event: ft.ControlEvent,
                text_control=label_text,
            ) -> None:
                hovered = is_hover(event)
                text_control.color = (
                    link_hover_color(page) if hovered else fg
                )
                try:
                    text_control.update()
                except Exception:
                    pass

            label.on_hover = on_label_hover
            track = ft.Container(
                width=bar_width,
                height=TAG_BAR_HEIGHT,
                border_radius=TAG_BAR_HEIGHT / 2,
                bgcolor=ft.Colors.with_opacity(0.12, fg),
                content=ft.Row(spacing=0, controls=[fill]),
            )
            rows.append(
                ft.Row(
                    spacing=gap,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        label_gesture,
                        track,
                        ft.Container(
                            width=count_width,
                            alignment=ft.Alignment.CENTER_RIGHT,
                            content=ui_text(
                                str(count),
                                size=12,
                                color=fg,
                            ),
                        ),
                    ],
                )
            )
        return ft.Column(
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            controls=rows,
        )

    page_col = scroll_page([body])
    view = ft.View(
        route="/statistics/tags",
        appbar=ft.AppBar(title=ui_text("标签")),
        padding=page_padding(),
        controls=[page_col],
    )
    view.data = {
        "rebuild": lambda: tags_view(page),
        "tag_filters": selected,
    }
    scroll_memory.remember(page, "/statistics/tags", "page", page_col)
    scroll_memory.schedule_restore(page, view)

    def rebuild(*, animate: bool) -> None:
        width = _tags_target_width(page)
        content_width["value"] = width
        chart_holder.width = width
        filter_block.width = width
        chips_row.width = width
        chips_row.controls = [chip_control(tag) for tag in selected]
        chart_holder.controls = [build_chart(width, animate=animate)]
        anim_state["run"] = animate

    rebuild(animate=play_animation)
    refresh_filters()

    async def animate_bars() -> None:
        if not await wait_until_ready(page, chart_holder):
            return
        for fill, ratio, bar_width in bar_specs:
            fill.width = bar_width * ratio
        try:
            page.update(*(fill for fill, _, _ in bar_specs))
        except RuntimeError:
            return
        except Exception:
            pass

    previous_resize = page.on_resize

    def on_resize(event: ft.ControlEvent | None = None) -> None:
        if view in page.views and page.views[-1] is view:
            rebuild(animate=False)
            return
        if (
            previous_resize is not None
            and previous_resize is not on_resize
        ):
            previous_resize(event)

    page.on_resize = on_resize
    if play_animation:
        page.run_task(animate_bars)
    return view


