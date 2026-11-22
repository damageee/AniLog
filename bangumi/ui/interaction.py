"""悬停、点击与复制等交互辅助。"""

from __future__ import annotations

import asyncio
import dataclasses
import math
import weakref

import flet as ft
from bangumi.ui.events import is_hover
from bangumi.ui.platform import is_mobile

from bangumi.ui.colors import (
    foreground_color,
    link_hover_color,
)
from bangumi.ui.constants import (
    ANIM_ICON_MS,
    ANIM_SLOW_MS,
    HOVER_SCALE_IMAGE,
    ICON_HOVER_OPACITY,
)
from bangumi.ui.theme import ui_text


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

    def reset_hover() -> None:
        # 点击后页面通常切换，指针不会再发 hover 离开事件，先复位。
        text.color = base_color
        try:
            text.update()
        except Exception:
            pass

    def on_click_reset(event: ft.ControlEvent) -> None:
        reset_hover()
        if callable(on_click):
            on_click(event)

    holder = ft.Container(content=text, on_click=on_click_reset)

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
    # 视图离开栈顶时复位颜色，避免返回后停在 hover 态。
    from bangumi.ui.hover_state import register

    register(holder, reset_hover)
    return holder


def hover_copy(
    page: ft.Page,
    text: ft.Text,
    on_click,
) -> ft.Container:
    """悬停时显示下划线的可点击复制文本，颜色不变。"""
    base_style = text.style

    def reset_hover() -> None:
        # 点击后指针可能不再回到本控件，先把样式复位。
        text.style = base_style
        try:
            text.update()
        except Exception:
            pass

    def on_click_reset(event: ft.ControlEvent) -> None:
        reset_hover()
        if callable(on_click):
            on_click(event)

    holder = ft.Container(content=text, on_click=on_click_reset)

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
    # 视图离开栈顶时复位下划线样式。
    from bangumi.ui.hover_state import register

    register(holder, reset_hover)
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

    def reset_icon_hover() -> None:
        # 只改属性，不 update：此时视图正在卸载。
        holder.bgcolor = ft.Colors.TRANSPARENT

    from bangumi.ui.hover_state import register

    register(holder, reset_icon_hover)

    previous_click = holder.on_click
    if callable(previous_click):
        def on_click_reset(event: ft.ControlEvent) -> None:
            # 先复位光晕，避免返回时图标停在 hover 状态。
            holder.bgcolor = ft.Colors.TRANSPARENT
            try:
                holder.update()
            except Exception:
                pass
            previous_click(event)

        holder.on_click = on_click_reset

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
    inner = ft.Container(
        content=control,
        scale=1.0,
        animate_scale=_anim(ANIM_SLOW_MS),
    )
    state = {"scale": 1.0}

    def apply(on: bool) -> None:
        target = scale if on else 1.0
        if state["scale"] == target:
            return
        state["scale"] = target
        inner.scale = target
        try:
            inner.update()
        except Exception:
            pass

    sensor = ft.GestureDetector(
        on_enter=lambda event: apply(True),
        on_exit=lambda event: apply(False),
        content=inner,
    )

    def reset_zoom() -> None:
        # 只改属性，不 update：此时视图正在卸载。
        inner.scale = 1.0

    from bangumi.ui.hover_state import register

    register(inner, reset_zoom)
    return ft.Container(content=sensor)


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

    def is_top() -> bool:
        """仅栈顶视图处理尺寸/滚动事件，避免背景页事件堆积。"""
        return bool(page.views) and page.views[-1] is view

    state: dict[str, object] = {
        "pixels": 0.0,
    }
    holder: ft.Container | None = None
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
        current = [
            child
            for child in (getattr(scroller, "controls", None) or [])
            if isinstance(child, ft.Control)
        ]
        if not current:
            apply_extent(0)
            return
        if viewport is None:
            return
        if any(id(child) not in child_heights for child in current):
            return
        total = sum(
            child_heights[id(child)] for child in current
        ) + spacing * max(0, len(current) - 1)
        apply_extent(total - float(viewport))

    def refresh_visibility() -> None:
        """按当前子控件重新绑定尺寸监听并计算显隐。"""
        current = [
            child
            for child in (getattr(scroller, "controls", None) or [])
            if isinstance(child, ft.Control)
        ]
        for child in current:
            if getattr(child, "_scroll_bottom_bound", False):
                continue
            previous_child = getattr(
                child, "on_size_change", None
            )

            def update_child(
                event: ft.ControlEvent,
                target=child,
                previous_handler=previous_child,
            ) -> None:
                if not is_top():
                    return
                height = getattr(event, "height", None)
                if isinstance(height, (int, float)):
                    child_heights[id(target)] = float(height)
                evaluate_sizes()
                if callable(previous_handler):
                    previous_handler(event)

            child.on_size_change = update_child
            child._scroll_bottom_bound = True
        evaluate_sizes()

    def on_scroll(event: ft.OnScrollEvent) -> None:
        # 非栈顶时直接交给原处理器并返回，避免无谓计算。
        if not is_top():
            if callable(original):
                original(event)
            return
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
    holder._scroll_bottom_refresh = refresh_visibility

    scroller.on_scroll = on_scroll

    def update_viewport(event: ft.ControlEvent) -> None:
        # 非栈顶视图不必更新尺寸。
        if not is_top():
            return
        height = getattr(event, "height", None)
        if isinstance(height, (int, float)):
            size_state["viewport"] = float(height)
        evaluate_sizes()

    previous_viewport = getattr(scroller, "on_size_change", None)

    def on_scroller_size(
        event: ft.ControlEvent,
        previous_handler=previous_viewport,
    ) -> None:
        # 非栈顶时只转交原处理器。
        if not is_top():
            if callable(previous_handler):
                previous_handler(event)
            return
        update_viewport(event)
        if callable(previous_handler):
            previous_handler(event)

    scroller.on_size_change = on_scroller_size

    refresh_visibility()

    return holder


def set_scroll_bottom_visible(
    page: ft.Page,
    view: ft.View,
    visible: bool | None = None,
) -> None:
    """按内容状态强制显示/隐藏，或重算滚动到底部箭头。"""
    appbar = getattr(view, "appbar", None)
    actions = list(getattr(appbar, "actions", None) or [])
    for action in actions:
        data = getattr(action, "data", None)
        if data is None:
            data = getattr(
                getattr(action, "content", None),
                "data",
                None,
            )
        if data != SCROLL_BOTTOM_MARKER:
            continue
        if visible is None:
            refresh = getattr(
                action, "_scroll_bottom_refresh", None
            )
            if callable(refresh):
                refresh()
            return
        opacity = 1.0 if visible else 0.0
        ignore = not visible
        if (
            getattr(action, "opacity", None) == opacity
            and getattr(action, "ignore_interactions", None) == ignore
        ):
            return
        action.opacity = opacity
        action.ignore_interactions = ignore
        try:
            action.update()
        except Exception:
            pass
        return


def tooltip_colors(page: ft.Page) -> tuple[str, str]:
    """返回与系统 tooltip 一致的 (背景色, 文字色)。"""
    dark = page.theme_mode == ft.ThemeMode.DARK
    return (
        "#E6E6E6" if dark else "#616161",
        "#1F1F1F" if dark else "#FFFFFF",
    )


class FloatingLabel:
    """移动端长按图表时跟随手指的标签。"""

    def __init__(self, page: ft.Page) -> None:
        global _LABEL_HOOKS_INSTALLED

        self.page = page
        bubble_bg, bubble_fg = tooltip_colors(page)
        self.text = ft.Text(
            "",
            size=12,
            color=bubble_fg,
            no_wrap=True,
        )
        self.holder = ft.Container(
            visible=False,
            ignore_interactions=True,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.95, bubble_bg),
            content=self.text,
        )
        _LIVE_LABELS[:] = [
            ref for ref in _LIVE_LABELS if ref() is not None
        ]
        _LIVE_LABELS.append(weakref.ref(self))
        if not _LABEL_HOOKS_INSTALLED:
            from bangumi.views.navigation.stack import (
                register_navigation_hook,
            )

            register_navigation_hook(_hide_all_labels)
            _LABEL_HOOKS_INSTALLED = True
        self._hooks_installed = _LABEL_HOOKS_INSTALLED

    def show(self, event: ft.ControlEvent, message: str) -> None:
        from bangumi.ui.text_metrics import text_width
        from bangumi.ui.events import event_position

        # 同时只保留一个气泡。
        for ref in list(_LIVE_LABELS):
            other = ref()
            if other is not None and other is not self:
                other.hide()

        self.text.value = message
        width = max(60.0, text_width(message, size=12) + 24)
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
        mounted = self.holder in self.page.overlay
        self.holder.width = width
        self.holder.left = left
        self.holder.top = max(8, top)
        self.holder.visible = True
        bubble_bg, bubble_fg = tooltip_colors(self.page)
        self.holder.bgcolor = ft.Colors.with_opacity(0.95, bubble_bg)
        if self.text is not None:
            self.text.color = bubble_fg
        if not mounted:
            self.page.overlay.append(self.holder)
            try:
                self.page.update()
            except Exception:
                pass
            return
        try:
            self.holder.update()
        except Exception:
            try:
                self.page.update()
            except Exception:
                pass

    def hide(
        self,
        *,
        detach: bool = False,
        update: bool = True,
    ) -> None:
        if detach and self.holder in self.page.overlay:
            self.page.overlay.remove(self.holder)
        elif detach:
            pass
        if not self.holder.visible and not detach:
            return
        self.holder.visible = False
        if not update:
            return
        try:
            self.holder.update()
        except Exception:
            pass


_LIVE_LABELS: list[weakref.ref] = []
_LABEL_HOOKS_INSTALLED = False


def _hide_all_labels(page: ft.Page) -> None:
    for ref in list(_LIVE_LABELS):
        label = ref()
        if label is None:
            _LIVE_LABELS.remove(ref)
            continue
        label.hide(detach=True, update=False)


def hide_all_labels(page: ft.Page) -> None:
    """清理所有悬浮标签（resize 等场景）。"""
    _hide_all_labels(page)


class ClickableText:
    """带 hover 效果的可点击文本。统一入口，避免各处重复写 on_hover。"""

    def __init__(
        self,
        page: ft.Page,
        text: str,
        *,
        size: int = 14,
        color: str | None = None,
        weight: ft.FontWeight | None = None,
        no_wrap: bool = False,
        max_lines: int | None = None,
        overflow: ft.TextOverflow | None = None,
        on_click=None,
        tooltip: str | None = None,
    ) -> None:
        self.page = page
        base = color or foreground_color(page)
        kwargs = {}
        if no_wrap:
            kwargs["no_wrap"] = True
        if max_lines is not None:
            kwargs["max_lines"] = max_lines
        if overflow is not None:
            kwargs["overflow"] = overflow
        self.text = ui_text(
            text,
            size=size,
            color=base,
            weight=weight,
            **kwargs,
        )
        self.control = ft.Container(
            content=self.text,
            on_click=on_click,
            tooltip=tooltip,
        )

        def on_hover(event: ft.ControlEvent) -> None:
            hovered = is_hover(event)
            self.text.color = link_hover_color(page) if hovered else base
            try:
                self.text.update()
            except Exception:
                pass

        self.control.on_hover = on_hover
