"""统计页面的浮层、引用气泡与定位辅助。"""

from __future__ import annotations

import re
import flet as ft
from bangumi.ui.text_metrics import (
    text_width,
)
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.ui.events import event_position
from bangumi.views.statistics.common.shared import (
    BOTTOM_SAFE_MARGIN,
    OVERLAY_MARGIN,
    PANEL_OFFSET,
    PANEL_SIDE_RESERVE,
    _legend_panel,
    _panel_size,
)


class _PanelOverlay:
    """在 ``page.overlay`` 中一次承载一个浮动图例面板。"""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.active: ft.Container | None = None

    def _detach(self) -> bool:
        panel = self.active
        self.active = None
        if panel is None:
            return False
        if panel in self.page.overlay:
            self.page.overlay.remove(panel)
            return True
        if panel.visible:
            panel.visible = False
            return True
        return False

    def show(self, panel: ft.Container) -> None:
        # 该面板只挂载到 page.overlay（窗口级），
        # 从不挂载到环形区块或任何卡片/滚动控件树。
        if panel is self.active and panel in self.page.overlay:
            return
        self._detach()
        panel.visible = True
        if panel not in self.page.overlay:
            self.page.overlay.append(panel)
        self.active = panel
        self.page.update()

    def hide(self, *, update: bool = True) -> None:
        if self._detach() and update:
            self.page.update()


class _OverlayLayers:
    """管理独立的窗口级图层（标签、引用）。"""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.layers: list[ft.Container] = []

    def show(self, panel: ft.Container) -> None:
        panel.visible = True
        if panel in self.page.overlay:
            try:
                panel.update()
            except Exception:
                self.page.update()
        else:
            self.page.overlay.append(panel)
            self.page.update()
        if panel not in self.layers:
            self.layers.append(panel)

    def remove(self, panel: ft.Container) -> None:
        panel.visible = False
        if panel in self.page.overlay:
            try:
                panel.update()
            except Exception:
                self.page.update()
        elif panel in self.layers:
            self.layers.remove(panel)

    def hide(self, *, update: bool = True) -> None:
        changed = False
        for panel in list(self.layers):
            panel.visible = False
            if panel in self.page.overlay:
                self.page.overlay.remove(panel)
                changed = True
        self.layers.clear()
        if changed and update:
            self.page.update()


_PAGE_OVERLAYS: dict[int, _PanelOverlay | _OverlayLayers] = {}


def _register_overlay(
    page: ft.Page,
    overlay: _PanelOverlay | _OverlayLayers,
) -> None:
    previous = _PAGE_OVERLAYS.get(id(page))
    if previous is not None and previous is not overlay:
        previous.hide()
    _PAGE_OVERLAYS[id(page)] = overlay


def _install_overlay_hook(page: ft.Page) -> None:
    from bangumi.views.navigation.stack import register_navigation_hook

    register_navigation_hook(_hide_page_overlay_silent)
    previous_route = page.on_route_change
    if not getattr(previous_route, "_statistics_overlay_hook", False):

        def route_change(event: ft.RouteChangeEvent) -> None:
            overlay = _PAGE_OVERLAYS.get(id(page))
            if overlay is not None:
                overlay.hide()
            if previous_route is not None:
                previous_route(event)

        route_change._statistics_overlay_hook = True
        page.on_route_change = route_change

    previous_pop = page.on_view_pop
    if not getattr(previous_pop, "_statistics_overlay_hook", False):

        async def view_pop(event: ft.ViewPopEvent) -> None:
            overlay = _PAGE_OVERLAYS.get(id(page))
            if overlay is not None:
                overlay.hide()
            if previous_pop is not None:
                result = previous_pop(event)
                if result is not None and hasattr(result, "__await__"):
                    await result

        view_pop._statistics_overlay_hook = True
        page.on_view_pop = view_pop


def _hide_page_overlay(page: ft.Page) -> None:
    overlay = _PAGE_OVERLAYS.get(id(page))
    if overlay is not None:
        overlay.hide()


def _hide_page_overlay_silent(page: ft.Page) -> None:
    overlay = _PAGE_OVERLAYS.get(id(page))
    if overlay is not None:
        overlay.hide(update=False)


def _page_width(page: ft.Page) -> float:
    return float(page.width or 1000)


def _page_height(page: ft.Page) -> float:
    return float(page.height or 800)


def _page_dimensions(page: ft.Page) -> tuple[float, float]:
    return _page_width(page), _page_height(page)


def _overlay_placement(
    page: ft.Page,
    event: ft.ControlEvent,
    *,
    width: float,
    height: float,
    bottom_reserve: float = 0.0,
) -> dict[str, float]:
    x, y = event_position(event)
    page_width = _page_width(page)
    page_height = _page_height(page)
    left = min(
        max(x - width / 2, OVERLAY_MARGIN),
        max(OVERLAY_MARGIN, page_width - OVERLAY_MARGIN - width),
    )
    top = y + PANEL_OFFSET
    bottom_limit = page_height - OVERLAY_MARGIN - bottom_reserve
    if top + height > bottom_limit:
        top = y - PANEL_OFFSET - height
    top = max(
        OVERLAY_MARGIN,
        min(top, max(OVERLAY_MARGIN, bottom_limit - height)),
    )
    return {"left": left, "top": top}


def _adjacent_panel_position(
    page: ft.Page,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> tuple[float, float] | None:
    page_width = _page_width(page)
    page_height = _page_height(page)
    x = min(max(float(x), 0.0), page_width)
    y = min(max(float(y), 0.0), page_height)

    horizontal: list[float] = []
    right = x + PANEL_OFFSET
    left = x - PANEL_OFFSET - width
    if (
        right + width
        <= page_width - OVERLAY_MARGIN - PANEL_SIDE_RESERVE
    ):
        horizontal.append(right)
    if left >= OVERLAY_MARGIN:
        horizontal.append(left)
    centered_horizontal = min(
        max(x - width / 2, OVERLAY_MARGIN),
        max(OVERLAY_MARGIN, page_width - OVERLAY_MARGIN - width),
    )
    if centered_horizontal not in horizontal:
        horizontal.append(centered_horizontal)

    vertical: list[float] = []
    below = y + PANEL_OFFSET
    above = y - PANEL_OFFSET - height
    bottom_limit = page_height - OVERLAY_MARGIN - BOTTOM_SAFE_MARGIN
    if below + height <= bottom_limit:
        vertical.append(below)
    if above >= OVERLAY_MARGIN:
        vertical.append(above)
    centered_vertical = min(
        max(y - height / 2, OVERLAY_MARGIN),
        max(OVERLAY_MARGIN, bottom_limit - height),
    )
    if centered_vertical not in vertical:
        vertical.append(centered_vertical)

    for left_value in horizontal:
        for top_value in vertical:
            if (
                left_value >= OVERLAY_MARGIN
                and top_value >= OVERLAY_MARGIN
                and left_value + width
                <= page_width - OVERLAY_MARGIN
                and top_value + height
                <= bottom_limit
            ):
                return left_value, top_value
    return None


def _corner_panel_position(
    page: ft.Page,
    *,
    width: float,
    height: float,
) -> tuple[float, float] | None:
    page_width = _page_width(page)
    page_height = _page_height(page)
    bottom_limit = page_height - OVERLAY_MARGIN - BOTTOM_SAFE_MARGIN
    corners = (
        (page_width - OVERLAY_MARGIN - width, OVERLAY_MARGIN),
        (OVERLAY_MARGIN, OVERLAY_MARGIN),
        (
            page_width - OVERLAY_MARGIN - width,
            bottom_limit - height,
        ),
        (OVERLAY_MARGIN, bottom_limit - height),
    )
    for left, top in corners:
        if (
            left >= OVERLAY_MARGIN
            and top >= OVERLAY_MARGIN
            and left + width <= page_width - OVERLAY_MARGIN
            and top + height <= bottom_limit
        ):
            return left, top
    return None


def _overlay_panel_position(
    page: ft.Page,
    *,
    x: float,
    y: float,
    rows: int,
) -> tuple[bool, float, float]:
    for compact in (False, True):
        width, height = _panel_size(rows, compact)
        position = _adjacent_panel_position(
            page,
            x=x,
            y=y,
            width=width,
            height=height,
        )
        if position is not None:
            return compact, position[0], position[1]
        position = _corner_panel_position(
            page,
            width=width,
            height=height,
        )
        if position is not None:
            return compact, position[0], position[1]

    width, _ = _panel_size(rows, True)
    page_width = _page_width(page)
    left = min(
        max((page_width - width) / 2, OVERLAY_MARGIN),
        max(OVERLAY_MARGIN, page_width - OVERLAY_MARGIN - width),
    )
    return True, left, OVERLAY_MARGIN


QUOTES = {
    "春": (
        "我喜欢了你十年，却用一整个四月，编织了一个我不爱你的谎言。",
        "樱花满地集于我心，楪舞纷飞祈愿相随。",
        "你驻足于春色之中，于那独一无二的春色之中。",
        "春天马上就要来了。",
        "花无凋零之日，意无传递之时，爱情亘古不变，紫罗兰与世长存。",
        "未闻花名，但识花香，再遇花时，泪已千行。",
    ),
    "夏": (
        "转瞬即逝的相逢与离别，每一个瞬间，我都想要珍惜。",
        "过来，萤。我终于能触碰你了。",
        "音无结弦之时，悦动天使之心；立于浮华之世，奏响天籁之音。",
        "唯有那份炫目 未曾忘却",
        "无论何时，我都会记得夏天的蓝。",
    ),
    "秋": (
        "心虽有所觉，但亦作不解。",
        "折木弄花千蝶反田，蔷薇穹下旷世恋语。",
    ),
    "冬": (
        "又到了白色相簿的季节。",
        "所以，把扭曲你人生的权利交给我。",
        "只愿，你和这个将你包围的世界，能够永远幸福。",
        "どうか、君と君を囲むこの世界が、これからも幸せでありますように。",
    ),
}


_QUOTE_CHUNK_RE = re.compile(r"[^，。；！？、,;!?]*[，。；！？、,;!?]?")


def _wrap_quote(value: str, max_width: int, *, size: int = 12) -> str:
    text = f"“{value}”"
    chunks = [
        chunk for chunk in _QUOTE_CHUNK_RE.findall(text) if chunk
    ]
    lines: list[str] = []
    line = ""
    for chunk in chunks:
        candidate = line + chunk
        if line and text_width(candidate, size=size) > max_width:
            lines.append(line)
            line = chunk
        else:
            line = candidate
        while (
            line
            and text_width(line, size=size) > max_width
            and len(line) > 1
        ):
            cut = len(line) - 1
            while (
                cut > 1
                and text_width(line[:cut], size=size) > max_width
            ):
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line:
        lines.append(line)
    return "\n".join(lines)


def _quote_metrics(page: ft.Page, quote: str) -> tuple[float, float]:
    page_width = float(page.width or 900)
    width = min(
        max(220, int(page_width * 0.42)),
        max(160, int(page_width) - 24),
        440,
    )
    lines = _wrap_quote(quote, width - 24, size=12).count("\n") + 1
    height = lines * 22 + 24
    return float(width), float(height)


def _quote_overlay(
    page: ft.Page,
    quote: str,
    *,
    panel: ft.Container | None = None,
) -> tuple[ft.Container, float]:
    page_width = float(page.width or 900)
    width = min(
        max(220, int(page_width * 0.42)),
        max(160, int(page_width) - 24),
        440,
    )
    text = _wrap_quote(quote, width - 24, size=12)
    height = (text.count("\n") + 1) * 22 + 24
    if panel is None:
        panel = ft.Container(
            left=12,
            bottom=12,
            width=width,
            ignore_interactions=True,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=10,
            bgcolor=background_color(page),
            border=ft.Border.all(
                1,
                ft.Colors.with_opacity(
                    0.2,
                    foreground_color(page),
                ),
            ),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                offset=ft.Offset(2, 4),
            ),
            content=ui_text(
                text,
                size=12,
                italic=True,
                color=foreground_color(page),
            ),
        )
    else:
        panel.width = width
        if isinstance(panel.content, ft.Text):
            panel.content.value = text
        else:
            panel.content = ui_text(
                text,
                size=12,
                italic=True,
                color=foreground_color(page),
            )
    return panel, float(height)


def _ring_block(
    page: ft.Page,
    *,
    title: str,
    ring: ft.Control,
    accent: str,
    col: dict[str, int],
    panel_title: str,
    panel_rows: list[tuple[str, int, str]],
    overlay: _PanelOverlay,
) -> ft.Control:
    panels: dict[bool, ft.Container] = {}
    row_count = len(panel_rows)

    def panel_for(compact: bool) -> ft.Container:
        if compact not in panels:
            panels[compact] = _legend_panel(
                page,
                title=panel_title,
                rows=panel_rows,
                accent=accent,
                compact=compact,
            )
        return panels[compact]

    def own_panel_active() -> bool:
        return overlay.active is not None and any(
            overlay.active is panel for panel in panels.values()
        )

    def show_panel(event: ft.ControlEvent, *, toggle: bool) -> None:
        x, y = event_position(event)
        compact, left, top = _overlay_panel_position(
            page,
            x=x,
            y=y,
            rows=row_count,
        )
        panel = panel_for(compact)
        if toggle and own_panel_active():
            overlay.hide()
            return
        panel.left = left
        panel.top = top
        panel.bottom = None
        overlay.show(panel)

    def on_enter(event: ft.ControlEvent) -> None:
        show_panel(event, toggle=False)

    def on_exit(event: ft.ControlEvent) -> None:
        if own_panel_active():
            overlay.hide()

    def on_tap(event: ft.ControlEvent) -> None:
        show_panel(event, toggle=True)

    return ft.GestureDetector(
        col=col,
        on_enter=on_enter,
        on_exit=on_exit,
        on_tap=on_tap,
        content=ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=14,
            bgcolor=ft.Colors.with_opacity(0.03, accent),
            content=ft.Column(
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ui_text(
                        title,
                        size=16,
                        color=ft.Colors.with_opacity(
                            0.75,
                            foreground_color(page),
                        ),
                    ),
                    ring,
                ],
            ),
        ),
    )


