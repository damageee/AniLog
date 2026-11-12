"""悬停、点击与复制等交互辅助。"""

from __future__ import annotations

import asyncio
import dataclasses
import math

import flet as ft
from bangumi.ui.events import is_hover
from bangumi.ui.platform import is_mobile

from bangumi.ui.colors import (
    background_color,
    foreground_color,
    link_hover_color,
)
from bangumi.ui.constants import (
    ANIM_ICON_MS,
    ANIM_SLOW_MS,
    HOVER_SCALE_IMAGE,
    ICON_HOVER_OPACITY,
)


def _anim(ms: int):
    from bangumi.ui.anim import animation

    return animation(ms)


def hover_link(
    page: ft.Page,
    text: ft.Text,
    base_color: str,
    on_click,
) -> ft.Container:
    """悬停时变为浅蓝色的可点击文本。"""
    holder = ft.Container(content=text, on_click=on_click)

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        text.color = (
            link_hover_color(page) if hovered else base_color
        )
        try:
            text.update()
        except Exception:
            pass

    holder.on_hover = on_hover
    return holder


def hover_copy(
    page: ft.Page,
    text: ft.Text,
    on_click,
) -> ft.Container:
    """悬停时显示下划线的可点击复制文本，颜色不变。"""
    holder = ft.Container(content=text, on_click=on_click)
    base_style = text.style

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        if hovered:
            style = (
                dataclasses.replace(base_style)
                if base_style
                else ft.TextStyle()
            )
            style.decoration = ft.TextDecoration.UNDERLINE
            text.style = style
        else:
            text.style = base_style
        try:
            text.update()
        except Exception:
            pass

    holder.on_hover = on_hover
    return holder


def hover_icon(
    page: ft.Page,
    icon: str,
    *,
    on_click,
    tooltip: str | ft.Tooltip | None = None,
    size: int = 20,
    color: str | None = None,
    padding: int = 5,
    disabled: bool = False,
) -> ft.Container:
    """悬停时带柔和光晕的可点击图标。"""
    icon_color = color or foreground_color(page)
    if disabled:
        icon_color = ft.Colors.with_opacity(0.35, icon_color)
    holder = ft.Container(
        padding=ft.Padding.all(padding),
        border_radius=999,
        animate=_anim(ANIM_ICON_MS),
        bgcolor=ft.Colors.TRANSPARENT,
        tooltip=tooltip,
        on_click=None if disabled else on_click,
        content=ft.Icon(
            icon,
            size=size,
            color=icon_color,
        ),
    )
    if disabled:
        return holder
    glow = ft.Colors.with_opacity(
        ICON_HOVER_OPACITY, foreground_color(page)
    )

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        holder.bgcolor = glow if hovered else ft.Colors.TRANSPARENT
        try:
            holder.update()
        except Exception:
            pass

    holder.on_hover = on_hover

    if not disabled and is_mobile(page):
        async def flash() -> None:
            holder.bgcolor = glow
            try:
                holder.update()
            except Exception:
                pass
            await asyncio.sleep(ANIM_ICON_MS / 1000)
            holder.bgcolor = ft.Colors.TRANSPARENT
            try:
                holder.update()
            except Exception:
                pass

        def on_click_with_flash(event: ft.ControlEvent) -> None:
            page.run_task(flash)
            if on_click is not None:
                on_click(event)

        holder.on_click = on_click_with_flash

    return holder


def back_icon(
    page: ft.Page,
    route: str,
    *,
    before=None,
) -> ft.Container:
    """共用的返回箭头控件。"""
    def on_click(event: ft.ControlEvent) -> None:
        from bangumi.views.navigation import go_back

        go_back(page, route, before)

    return hover_icon(
        page,
        ft.Icons.ARROW_BACK,
        on_click=on_click,
        tooltip="返回",
        padding=8,
    )


def hover_zoom(
    page: ft.Page,
    control: ft.Control,
    *,
    scale: float = HOVER_SCALE_IMAGE,
) -> ft.Container:
    """包装控件，使其在悬停时略微放大。"""
    holder = ft.Container(content=control)
    holder.animate_scale = _anim(ANIM_SLOW_MS)
    holder.scale = 1.0

    def on_hover(event: ft.ControlEvent) -> None:
        hovered = is_hover(event)
        holder.scale = scale if hovered else 1.0
        try:
            holder.update()
        except Exception:
            pass

    holder.on_hover = on_hover
    return holder


def is_attached(control: ft.Control | None) -> bool:
    """仅当控件已挂载到页面时返回 True。"""
    if control is None:
        return False
    try:
        return control.page is not None
    except RuntimeError:
        return False


SCROLL_BOTTOM_MARKER = "scroll-bottom"


def _is_vertical_scroller(control: ft.Control) -> bool:
    scroll = getattr(control, "scroll", None)
    if not scroll:
        return False
    if isinstance(scroll, ft.Scrollbar):
        return (
            getattr(scroll, "orientation", None)
            != ft.ScrollbarOrientation.BOTTOM
        )
    return not isinstance(control, ft.Row)


def _iter_child_controls(control: ft.Control):
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield content
    controls = getattr(control, "controls", None)
    if isinstance(controls, (list, tuple)):
        for child in controls:
            if isinstance(child, ft.Control):
                yield child


def find_vertical_scroller(view: ft.View) -> ft.Control | None:
    """广度优先找到视图里最外层的竖直滚动控件。"""
    queue = [
        control
        for control in (getattr(view, "controls", None) or [])
        if isinstance(control, ft.Control)
    ]
    seen: set[int] = set()
    while queue:
        control = queue.pop(0)
        if id(control) in seen:
            continue
        seen.add(id(control))
        if _is_vertical_scroller(control):
            return control
        queue.extend(_iter_child_controls(control))
    return None


def scroll_bottom_action(
    page: ft.Page,
    view: ft.View,
) -> ft.Container | None:
    """构造“滚动到底部”图标；没有竖直滚动容器时返回 None。"""
    from bangumi.ui.anim import animation
    from bangumi.ui.constants import ANIM_SLOW_MS

    scroller = find_vertical_scroller(view)
    if scroller is None:
        return None
    original = getattr(scroller, "on_scroll", None)
    state: dict[str, object] = {
        "pixels": 0.0,
    }
    holder: ft.Container | None = None
    children = [
        child
        for child in (getattr(scroller, "controls", None) or [])
        if isinstance(child, ft.Control)
    ]
    spacing = float(getattr(scroller, "spacing", 0) or 0)
    size_state: dict[str, float | None] = {"viewport": None}
    child_heights: dict[int, float] = {}

    async def to_bottom() -> None:
        from bangumi.ui.anim import duration
        from bangumi.ui.constants import SCROLL_TO_BOTTOM_MS

        try:
            await scroller.scroll_to(
                offset=-1,
                duration=duration(SCROLL_TO_BOTTOM_MS),
            )
        except Exception:
            pass

    def apply_extent(max_extent: object) -> None:
        nonlocal holder
        if holder is None:
            return
        visible = (
            isinstance(max_extent, (int, float))
            and math.isfinite(max_extent)
            and float(max_extent) > 0
        )
        opacity = 1.0 if visible else 0.0
        ignore = not visible
        if (
            holder.opacity == opacity
            and holder.ignore_interactions == ignore
        ):
            return
        holder.opacity = opacity
        holder.ignore_interactions = ignore
        try:
            holder.update()
        except Exception:
            pass

    def evaluate_sizes() -> None:
        viewport = size_state["viewport"]
        if viewport is None or not children:
            return
        if any(id(child) not in child_heights for child in children):
            return
        total = sum(
            child_heights[id(child)] for child in children
        ) + spacing * max(0, len(children) - 1)
        apply_extent(total - float(viewport))

    def on_scroll(event: ft.OnScrollEvent) -> None:
        state["pixels"] = float(
            getattr(event, "pixels", 0) or 0
        )
        apply_extent(getattr(event, "max_scroll_extent", None))
        if callable(original):
            original(event)

    holder = ft.Container(
        data=SCROLL_BOTTOM_MARKER,
        visible=True,
        opacity=0.0,
        ignore_interactions=True,
        animate_opacity=animation(ANIM_SLOW_MS),
        padding=ft.Padding.only(right=8),
        content=hover_icon(
            page,
            ft.Icons.ARROW_DOWNWARD,
            tooltip="滚动到底部",
            size=20,
            padding=8,
            on_click=lambda event: page.run_task(to_bottom),
        ),
    )

    scroller.on_scroll = on_scroll

    def update_viewport(event: ft.ControlEvent) -> None:
        height = getattr(event, "height", None)
        if isinstance(height, (int, float)):
            size_state["viewport"] = float(height)
        evaluate_sizes()

    previous_viewport = getattr(scroller, "on_size_change", None)

    def on_scroller_size(
        event: ft.ControlEvent,
        previous_handler=previous_viewport,
    ) -> None:
        update_viewport(event)
        if callable(previous_handler):
            previous_handler(event)

    scroller.on_size_change = on_scroller_size

    for child in children:
        previous_child = getattr(child, "on_size_change", None)

        def update_child(
            event: ft.ControlEvent,
            target=child,
            previous_handler=previous_child,
        ) -> None:
            height = getattr(event, "height", None)
            if isinstance(height, (int, float)):
                child_heights[id(target)] = float(height)
            evaluate_sizes()
            if callable(previous_handler):
                previous_handler(event)

        child.on_size_change = update_child

    return holder


class FloatingLabel:
    """移动端长按图表时跟随手指的标签。"""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.text = ft.Text("", size=11)
        self.holder = ft.Container(
            visible=False,
            ignore_interactions=True,
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
            border_radius=6,
            bgcolor=background_color(page),
            border=ft.Border.all(
                1,
                ft.Colors.with_opacity(0.25, foreground_color(page)),
            ),
            content=self.text,
        )

    def show(self, event: ft.ControlEvent, message: str) -> None:
        from bangumi.ui.text_metrics import text_width
        from bangumi.ui.events import event_position

        self.text.value = message
        width = max(60.0, text_width(message, size=11) + 20)
        x, y = event_position(event)
        page_width = float(self.page.width or 1000)
        page_height = float(self.page.height or 800)
        left = min(
            max(x - width / 2, 8),
            max(8.0, page_width - width - 8),
        )
        top = y - 44
        if top < 8:
            top = min(page_height - 40, y + 16)
        self.holder.width = width
        self.holder.left = left
        self.holder.top = max(8, top)
        self.holder.visible = True
        if self.holder not in self.page.overlay:
            self.page.overlay.append(self.holder)
        try:
            self.holder.update()
        except Exception:
            pass

    def hide(self) -> None:
        if not self.holder.visible:
            return
        self.holder.visible = False
        try:
            self.holder.update()
        except Exception:
            pass
