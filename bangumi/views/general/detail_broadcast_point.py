"""从观影表格的放送日期打开的放送月份浏览器。"""

from __future__ import annotations

import asyncio
import time

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.ui.interaction import hover_icon
from bangumi.core.utils import (
    add_months,
    month_from_value,
    month_value,
)
from bangumi.views.navigation import ENTRY
from bangumi.views.widgets.links import BROADCAST_DATE_RE, DetailLink
from bangumi.data.quarter_core import sort_records_by_broadcast
from bangumi.data.dates import parse_broadcast_date
from bangumi.data.watched_data import Record, load_records

_RADIUS = 24
_TRANSITION_SECONDS = 0.3
_TRANSITION_FRAME = 1.0 / 60.0
_VISUAL_INTERVAL = 0.06


class BroadcastPage:
    """放送月份浏览器的状态与 UI。"""

    def __init__(
        self,
        page: ft.Page,
        records: list[Record],
        clicked: Record,
        route: str,
    ) -> None:
        self.page = page
        self.records = records
        self.route = route
        self.foreground = foreground_color(page)

        parsed = parse_broadcast_date(
            str(clicked.get("broadcast", "") or "")
        )
        if parsed is None:
            for record in records:
                parsed = parse_broadcast_date(
                    str(record.get("broadcast", "") or "")
                )
                if parsed is not None:
                    break
        if parsed is None:
            parsed = (1970, 1, 1)
        self.year, self.month = parsed[0], parsed[1]

        if page.views:
            top = page.views[-1]
            if (
                str(getattr(top, "route", "")) == route
                and isinstance(getattr(top, "data", None), dict)
            ):
                remembered = top.data.get("centered_month")
                if (
                    isinstance(remembered, (tuple, list))
                    and len(remembered) == 2
                ):
                    self.year = int(remembered[0])
                    self.month = int(remembered[1])

        self._build_month_index()

        self.radius = _RADIUS
        self.viewport_width = max(
            300,
            int((page.width or 900) - 48),
        )
        if self.viewport_width >= 900:
            self.visible_boxes = 11
            span_factor = 6.45
        elif self.viewport_width >= 600:
            self.visible_boxes = 9
            span_factor = 5.54
        else:
            self.visible_boxes = 7
            span_factor = 4.55
        self.side = max(56, int(self.viewport_width / span_factor))
        self.step = (self.side + self.side * 0.93) / 2 * 0.66

        self.months_stack: ft.Stack
        self.box_centers: dict[int, float]
        self.box_base_scales: dict[int, float]
        self.box_controls: dict[int, ft.Container]
        self.box_dates: dict[int, ft.Text]
        self.box_counts: dict[int, ft.Text]
        self.stack_width: float
        self.center_x: float
        self.base_left: float
        self._build_stack()
        self.current_left = self.base_left
        self._last_visual_ts = 0.0
        self._transitioning = False
        self._transition_token = 0
        self._layer_center = 0

        self.strip_layer = ft.Container(
            content=self.months_stack,
            left=self.current_left,
            top=0,
        )
        self.viewport = ft.Container(
            width=self.viewport_width,
            height=self.side,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack(controls=[self.strip_layer]),
        )
        self.strip = ft.GestureDetector(
            on_pan_start=self._on_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            content=self.viewport,
        )
        self.title_text = ui_text(
            self._month_label(),
            size=28,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self.left_nav = ft.Row(tight=True, spacing=2)
        self.right_nav = ft.Row(tight=True, spacing=2)
        self.nav_row = ft.Row(
            width=self.viewport_width,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.left_nav,
                self.title_text,
                self.right_nav,
            ],
        )
        self._update_nav_buttons()
        self.list_column = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            controls=self._list_controls(),
        )

        content = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                self.strip,
                self.nav_row,
                self.list_column,
            ],
        )
        self.view = ft.View(
            route=route,
            appbar=ft.AppBar(title=ui_text("发布日")),
            padding=page_padding(),
            controls=[vertical_page([content])],
        )
        self.view.data = {
            "rebuild": lambda: build_broadcast_point_view(
                page, load_records(), clicked, route
            ),
            "centered_month": (self.year, self.month),
        }

    def _build_month_index(self) -> None:
        self.month_index: dict[str, list[Record]] = {}
        self.month_points: dict[str, tuple[int, int]] = {}
        for record in self.records:
            text = str(record.get("broadcast", "") or "")
            if "~" in text or "～" in text:
                continue
            points: set[tuple[int, int]] = set()
            for match in BROADCAST_DATE_RE.finditer(text):
                year, month, _ = match.groups()
                points.add((int(year), int(month)))
            for year, month in points:
                label = f"{year}年{month}月"
                self.month_points[label] = (year, month)
                self.month_index.setdefault(label, []).append(record)

        current = month_value(self.year, self.month)
        if self.month_points:
            values = [
                month_value(year, month)
                for year, month in self.month_points.values()
            ]
            self.min_value = min(values)
            self.max_value = max(values)
        else:
            self.min_value = current
            self.max_value = current
        self.min_value = min(self.min_value, current)
        self.max_value = max(self.max_value, current)

    def _month_records(self, label: str) -> list[Record]:
        return self.month_index.get(label, [])

    def _month_count(self, label: str) -> int:
        return len(self._month_records(label))

    def _month_label(self) -> str:
        return f"{self.year}年{self.month}月"

    def _nav_icon(
        self,
        icon: str,
        tooltip: str,
        *,
        on_click,
        disabled: bool = False,
    ) -> ft.Container:
        return hover_icon(
            self.page,
            icon,
            on_click=on_click,
            tooltip=tooltip,
            size=22,
            padding=6,
            color=self.foreground,
            disabled=disabled,
        )

    def _update_nav_buttons(self) -> None:
        current = month_value(self.year, self.month)
        values = sorted(
            {
                month_value(year, month)
                for year, month in self.month_points.values()
            }
        )
        prev_target = max(
            (value for value in values if value < current),
            default=None,
        )
        next_target = min(
            (value for value in values if value > current),
            default=None,
        )

        def move(months: int):
            def handler(event: ft.ControlEvent) -> None:
                self._move_months(months)

            return handler

        def jump(target: int | None):
            def handler(event: ft.ControlEvent) -> None:
                if target is None:
                    return
                self._animate_to_offset(
                    target - month_value(self.year, self.month)
                )

            return handler

        self.left_nav.controls = [
            self._nav_icon(
                ft.Icons.FAST_REWIND,
                "倒车三年",
                on_click=move(-36),
                disabled=current - 36 < self.min_value,
            ),
            self._nav_icon(
                ft.Icons.SKIP_PREVIOUS,
                "跳转到前一条",
                on_click=jump(prev_target),
                disabled=prev_target is None,
            ),
        ]
        self.right_nav.controls = [
            self._nav_icon(
                ft.Icons.SKIP_NEXT,
                "跳转到后一条",
                on_click=jump(next_target),
                disabled=next_target is None,
            ),
            self._nav_icon(
                ft.Icons.FAST_FORWARD,
                "前进三年",
                on_click=move(36),
                disabled=current + 36 > self.max_value,
            ),
        ]

    def _move_months(self, delta: int) -> None:
        current = month_value(self.year, self.month)
        target = min(
            max(current + delta, self.min_value),
            self.max_value,
        )
        if target != current:
            self._animate_to_offset(target - current)

    def _center_font_size(self) -> int:
        return max(13, min(18, int(self.side * 0.1)))

    def _build_stack(self) -> None:
        foreground = self.foreground
        dark = self.page.theme_mode == ft.ThemeMode.DARK
        background = ft.Colors.BLACK if dark else ft.Colors.WHITE

        widths: dict[int, float] = {}
        for offset in range(-self.radius, self.radius + 1):
            scale = max(0.62, 1.0 - 0.07 * abs(offset))
            widths[offset] = self.side * scale

        centers: dict[int, float] = {0: 0.0}
        for offset in range(1, self.radius + 1):
            step = (
                (widths[offset - 1] + widths[offset]) / 2
                * 0.66
            )
            centers[offset] = centers[offset - 1] + step
            centers[-offset] = centers[-offset + 1] - step

        existing: list[int] = []
        for offset in range(-self.radius, self.radius + 1):
            year, month = add_months(self.year, self.month, offset)
            value = month_value(year, month)
            if self.min_value <= value <= self.max_value:
                existing.append(offset)

        min_left = min(
            centers[offset] - widths[offset] / 2
            for offset in existing
        )
        max_right = max(
            centers[offset] + widths[offset] / 2
            for offset in existing
        )
        shift = -min_left
        for offset in centers:
            centers[offset] += shift

        self.box_centers = {
            offset: centers[offset] for offset in existing
        }
        self.stack_width = max_right - min_left
        self.center_x = centers[0]
        self.base_left = self.viewport_width / 2 - self.center_x

        self.box_controls = {}
        self.box_dates = {}
        self.box_counts = {}
        self.box_base_scales = {}
        center_size = self._center_font_size()
        side_size = max(12, center_size - 2)

        order = sorted(
            self.box_centers,
            key=lambda offset: abs(offset),
            reverse=True,
        )
        boxes: list[ft.Control] = []
        for offset in order:
            if offset not in self.box_centers:
                continue
            year, month = add_months(self.year, self.month, offset)
            label = f"{year}年{month}月"
            distance = abs(offset)
            width = widths[offset]
            center = offset == 0
            border_alpha = max(0.08, 0.85 - 0.12 * distance)
            count = self._month_count(label)
            count_color = self._count_color(count, dark)

            date_text = ui_text(
                label,
                size=center_size if center else side_size,
                weight=(
                    ft.FontWeight.BOLD
                    if center
                    else ft.FontWeight.NORMAL
                ),
                color=foreground,
                text_align=ft.TextAlign.CENTER,
                no_wrap=True,
            )
            layers: list[ft.Control] = [
                ft.Container(
                    width=width,
                    height=width,
                    alignment=ft.Alignment.CENTER,
                    content=date_text,
                )
            ]
            count_text: ft.Text | None = None
            if count > 0:
                count_text = ui_text(
                    str(count),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=count_color,
                    text_align=ft.TextAlign.CENTER,
                    no_wrap=True,
                )
                layers.append(
                    ft.Container(
                        width=width,
                        height=width,
                        alignment=ft.Alignment.BOTTOM_CENTER,
                        padding=ft.Padding.only(bottom=4),
                        content=count_text,
                    )
                )

            control = ft.Container(
                width=width,
                height=width,
                left=centers[offset] - width / 2,
                top=(self.side - width) / 2,
                alignment=ft.Alignment.CENTER,
                bgcolor=background,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                border=ft.Border.all(
                    1.5 if center else 1,
                    ft.Colors.with_opacity(
                        border_alpha,
                        foreground,
                    ),
                ),
                border_radius=8,
                on_click=(
                    lambda event, delta=offset: (
                        self._animate_to_offset(delta)
                    )
                ),
                content=ft.Stack(
                    width=width,
                    height=width,
                    controls=layers,
                ),
            )
            boxes.append(control)
            self.box_controls[offset] = control
            self.box_dates[offset] = date_text
            self.box_base_scales[offset] = (
                widths[offset] / self.side
            )
            if count_text is not None:
                self.box_counts[offset] = count_text

        self.months_stack = ft.Stack(
            width=self.stack_width,
            height=self.side,
            controls=boxes,
        )
        self._layer_center = 0

    def _count_color(self, count: int, dark: bool) -> str:
        if count >= 5:
            return ft.Colors.RED
        if count >= 3:
            return ft.Colors.ORANGE
        if count == 2:
            return ft.Colors.BLUE_300 if dark else ft.Colors.BLUE
        return ft.Colors.GREEN_300 if dark else ft.Colors.GREEN

    def _clamp_offset(self, delta_months: int) -> int:
        target = month_value(self.year, self.month) + delta_months
        target = min(max(target, self.min_value), self.max_value)
        year, month = month_from_value(target)
        return month_value(year, month) - month_value(
            self.year,
            self.month,
        )

    def select_offset(self, delta_months: int) -> None:
        self._transition_token += 1
        self._transitioning = False
        delta_months = self._clamp_offset(delta_months)
        self.year, self.month = add_months(
            self.year,
            self.month,
            delta_months,
        )
        self._build_stack()
        self.current_left = self.base_left
        self.strip_layer.content = self.months_stack
        self.strip_layer.left = self.current_left
        self.title_text.value = self._month_label()
        self.list_column.controls = self._list_controls()
        self._update_nav_buttons()
        data = self.view.data if isinstance(self.view.data, dict) else {}
        data["centered_month"] = (self.year, self.month)
        self.view.data = data
        self.page.update(
            self.strip_layer,
            self.title_text,
            self.list_column,
            self.left_nav,
            self.right_nav,
        )

    def _on_pan_start(self, event: ft.DragStartEvent) -> None:
        self._transition_token += 1
        self._transitioning = False
        self._last_visual_ts = 0.0

    def _on_pan_update(self, event: ft.DragUpdateEvent) -> None:
        local_delta = getattr(event, "local_delta", None)
        if local_delta is not None:
            dx = float(local_delta.x)
        else:
            dx = float(getattr(event, "primary_delta", 0) or 0)

        max_center = max(self.box_centers.values())
        min_center = min(self.box_centers.values())
        newest_limit = self.viewport_width / 2 - max_center
        oldest_limit = self.viewport_width / 2 - min_center
        self.current_left = min(
            max(self.current_left + dx, newest_limit),
            oldest_limit,
        )
        self.strip_layer.left = self.current_left

        now = time.monotonic()
        if now - self._last_visual_ts >= _VISUAL_INTERVAL:
            self._last_visual_ts = now
            self._apply_pan_visuals()
        self.strip_layer.update()

    def _update_layer_center(self, nearest: int) -> None:
        if nearest == self._layer_center:
            return
        self._layer_center = nearest
        ordered = sorted(
            self.box_centers,
            key=lambda offset: abs(offset - nearest),
            reverse=True,
        )
        self.months_stack.controls = [
            self.box_controls[offset] for offset in ordered
        ]

    def _apply_pan_visuals(self) -> None:
        viewport_center = self.viewport_width / 2 - self.current_left
        nearest = min(
            self.box_centers,
            key=lambda offset: abs(
                self.box_centers[offset] - viewport_center
            ),
        )
        self._update_layer_center(nearest)

        for offset, control in self.box_controls.items():
            center = self.box_centers[offset]
            distance_units = abs(center - viewport_center) / self.step
            target_scale = max(0.62, 1.0 - 0.07 * distance_units)
            border_alpha = max(0.08, 0.85 - 0.12 * distance_units)

            screen_center = center + self.current_left
            if (
                screen_center < -self.side
                or screen_center > self.viewport_width + self.side
            ):
                continue

            control.scale = target_scale / self.box_base_scales[offset]
            control.border = ft.Border.all(
                1.5 if offset == nearest else 1,
                ft.Colors.with_opacity(
                    border_alpha,
                    self.foreground,
                ),
            )

    def _on_pan_end(self, event: ft.DragEndEvent) -> None:
        self._apply_pan_visuals()
        self.strip_layer.left = self.current_left
        self.strip_layer.update()
        viewport_center = (
            self.viewport_width / 2 - self.current_left
        )
        nearest = min(
            self.box_centers,
            key=lambda offset: abs(
                self.box_centers[offset] - viewport_center
            ),
        )
        self.select_offset(nearest)

    def _animate_to_offset(self, offset: int) -> None:
        if self._transitioning:
            return

        target_offset = self._clamp_offset(offset)
        if target_offset not in self.box_centers:
            self.select_offset(target_offset)
            return

        target_left = (
            self.viewport_width / 2
            - self.box_centers[target_offset]
        )
        self._transition_token += 1
        token = self._transition_token
        self._transitioning = True
        self._last_visual_ts = 0.0
        self.page.run_task(
            self._transition_loop,
            token,
            self.current_left,
            target_left,
            target_offset,
        )

    async def _transition_loop(
        self,
        token: int,
        start_left: float,
        target_left: float,
        target_offset: int,
    ) -> None:
        started = time.monotonic()
        while True:
            if token != self._transition_token or not self._transitioning:
                return

            elapsed = time.monotonic() - started
            t = min(1.0, elapsed / _TRANSITION_SECONDS)
            ease = 1.0 - (1.0 - t) ** 3
            self.current_left = (
                start_left + (target_left - start_left) * ease
            )
            self._apply_pan_visuals()
            self.strip_layer.left = self.current_left
            self.strip_layer.update()

            if t >= 1.0:
                break
            await asyncio.sleep(_TRANSITION_FRAME)

        if token != self._transition_token or not self._transitioning:
            return
        self._transitioning = False
        self.select_offset(target_offset)

    def _list_controls(self) -> list[ft.Control]:
        label = self._month_label()
        records = sort_records_by_broadcast(
            self._month_records(label)
        )
        if not records:
            return [
                ui_text(
                    "",
                    size=14,
                    color=foreground_color(self.page),
                    text_align=ft.TextAlign.CENTER,
                )
            ]
        return [
            DetailLink(
                self.page,
                self.records,
                record,
                ENTRY,
                text=str(record.get("anime", "") or "").strip(),
                size=14,
                color=foreground_color(self.page),
            )
            for record in records
        ]


def build_broadcast_point_view(
    page: ft.Page,
    records: list[Record],
    clicked: Record,
    route: str,
) -> ft.View:
    return BroadcastPage(page, records, clicked, route).view


