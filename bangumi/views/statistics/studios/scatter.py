"""制作公司质量×产量散点页。"""

from __future__ import annotations

import statistics as stats_lib

import flet as ft

from bangumi.data.watched_data import load_records
from bangumi.ui.colors import background_color, foreground_color
from bangumi.ui.events import is_hover
from bangumi.ui.layout import vertical_page
from bangumi.ui.heat_zoom import animate_heat_cells
from bangumi.ui.anim import (
    animation,
    entry_animations_enabled,
)
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.ui.theme import ui_text
from bangumi.data.statistics.studios_honor import (
    _company_color,
    _honor_group,
)
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    _back_view,
)
from bangumi.ui.constants import (
    ANIM_BASE_MS,
)
from .homepage import open_studio_page


def studio_scatter_view(page: ft.Page) -> ft.View:
    records = load_records()
    route = "/statistics/studios/scatter"
    animate = entry_animations_enabled() and first_entry(page, route)
    if animate:
        mark_seen(page, route)
    fg = foreground_color(page)
    secondary = ft.Colors.with_opacity(0.55, fg)
    dark = page.theme_mode == ft.ThemeMode.DARK
    dot_controls: list[ft.Container] = []

    def build_view(
        *,
        entry_animation: bool = True,
    ) -> ft.View:
        available = max(
            120.0,
            float(page.width or 1000) - 48 - 16,
        )
        needed = 320.0
        chart_width = (
            available if available >= needed else needed
        )
        height = max(320.0, float(page.height or 800) - 140)
        left, top, right, bottom = 48.0, 48.0, 24.0, 56.0
        plot_w = max(1.0, chart_width - left - right)
        plot_h = max(1.0, height - top - bottom)

        groups = _honor_group(records)
        points = [
            (
                studio,
                int(item["count"]),
                float(item["avg"]),
                int(item["rated"]),
            )
            for studio, item in groups.items()
            if item["avg"] is not None
        ]
        works_values = [works for _, works, _, _ in points]
        avg_values = [avg for _, _, avg, _ in points]
        max_rated = max(
            (rated for _, _, _, rated in points),
            default=1,
        ) or 1
        x_min = 0.0
        x_max = max(works_values, default=1) or 1
        if avg_values:
            y_min = max(0.0, min(avg_values) - 2.0)
            y_max = min(100.0, max(avg_values) + 2.0)
        else:
            y_min, y_max = 0.0, 100.0
        if y_max <= y_min:
            y_max = min(100.0, y_min + 1.0)
        x_span = max(1.0, x_max - x_min)
        y_span = max(1.0, y_max - y_min)

        def px(value: float) -> float:
            return left + (value - x_min) / x_span * plot_w

        def py(value: float) -> float:
            return top + (1 - (value - y_min) / y_span) * plot_h

        x_mid = (
            float(stats_lib.median(works_values))
            if works_values
            else 0.0
        )
        y_mid = (
            float(stats_lib.median(avg_values))
            if avg_values
            else 0.0
        )
        grid = ft.Colors.with_opacity(0.25, fg)
        info_label = ft.Container(
            visible=False,
            left=8.0,
            top=8.0,
            ignore_interactions=True,
            padding=6,
            border_radius=6,
            bgcolor=background_color(page),
            content=ui_text("", size=11, color=fg),
        )
        controls: list[ft.Control] = [
            ft.Container(
                left=left,
                top=top,
                width=plot_w,
                height=plot_h,
                border=ft.Border.all(
                    1,
                    ft.Colors.with_opacity(0.15, fg),
                ),
            ),
            ft.Container(
                left=px(x_mid),
                top=top,
                width=1,
                height=plot_h,
                bgcolor=grid,
            ),
            ft.Container(
                left=left,
                top=py(y_mid),
                width=plot_w,
                height=1,
                bgcolor=grid,
            ),
        ]
        dot_points: list[
            tuple[float, float, str, float, int, ft.Container]
        ] = []
        active_dot: dict[str, ft.Container | None] = {"dot": None}

        def show_dot(
            target: ft.Container,
            studio_name: str,
            average: float,
            samples: int,
        ) -> None:
            previous = active_dot["dot"]
            if previous is not None and previous is not target:
                previous.scale = ft.Scale(1.0)
                try:
                    previous.update()
                except Exception:
                    pass
            info_label.content = ui_text(
                f"{studio_name} | 均分: "
                f"{average:.2f} ({samples}部)",
                size=11,
                color=fg,
            )
            info_label.left = max(
                8.0,
                float(target.left or 0) - 40,
            )
            info_label.top = max(
                8.0,
                float(target.top or 0) - 30,
            )
            info_label.visible = True
            target.scale = ft.Scale(1.2)
            active_dot["dot"] = target
            try:
                target.update()
            except Exception:
                pass
            try:
                info_label.update()
            except Exception:
                pass

        def hide_dot() -> None:
            target = active_dot["dot"]
            if target is not None:
                target.scale = ft.Scale(1.0)
                active_dot["dot"] = None
                try:
                    target.update()
                except Exception:
                    pass
            info_label.visible = False
            try:
                info_label.update()
            except Exception:
                pass

        def long_move(
            event: ft.ControlEvent,
            center_x: float,
            center_y: float,
        ) -> None:
            offset = getattr(event, "local_offset_from_origin", None)
            if offset is None:
                offset = getattr(event, "offset_from_origin", None)
            if offset is None:
                return
            finger_x = center_x + float(
                getattr(offset, "x", 0) or 0
            )
            finger_y = center_y + float(
                getattr(offset, "y", 0) or 0
            )
            nearest = None
            best = 1e9
            for (
                px_value,
                py_value,
                studio_name,
                average,
                samples,
                target,
            ) in dot_points:
                distance = (
                    (finger_x - px_value) ** 2
                    + (finger_y - py_value) ** 2
                ) ** 0.5
                if distance < best:
                    best = distance
                    nearest = (
                        target,
                        studio_name,
                        average,
                        samples,
                    )
            if nearest is not None and best < 40:
                show_dot(*nearest)
            else:
                hide_dot()

        for studio, works, avg, rated in points:
            diameter = 8 + (rated / max_rated) * 24
            radius = diameter / 2
            dot = ft.Container(
                left=px(works) - radius,
                top=py(avg) - radius,
                width=diameter,
                height=diameter,
                border_radius=radius,
                bgcolor=_company_color(studio, dark),
                on_click=(
                    lambda event, n=studio: open_studio_page(
                        page,
                        records,
                        n,
                    )
                ),
            )
            dot.animate_scale = animation(ANIM_BASE_MS)
            dot.animate_opacity = animation(220)
            entry = animate and entry_animation
            dot.opacity = 0 if entry else 1
            dot.scale = ft.Scale(1.4 if entry else 1.0)

            def on_hover(
                event: ft.ControlEvent,
                target=dot,
                studio_name=studio,
                works_count=works,
                average=avg,
                samples=rated,
            ) -> None:
                hovered = is_hover(event)
                target.scale = (
                    ft.Scale(1.2)
                    if hovered
                    else ft.Scale(1.0)
                )
                try:
                    target.update()
                except Exception:
                    pass
                if hovered:
                    info_label.content = ui_text(
                        f"{studio_name} | 均分: "
                        f"{average:.2f} ({samples}部)",
                        size=11,
                        color=fg,
                    )
                    info_label.left = max(
                        8.0,
                        float(target.left or 0) - 40,
                    )
                    info_label.top = max(
                        8.0,
                        float(target.top or 0) - 30,
                    )
                    info_label.visible = True
                else:
                    info_label.visible = False
                info_label.update()

            dot.on_hover = on_hover

            def open_dot(
                event: ft.ControlEvent,
                n=studio,
                target=dot,
            ) -> None:
                target.scale = ft.Scale(1.2)
                try:
                    target.update()
                except Exception:
                    pass
                open_studio_page(page, records, n)

            dot.on_click = open_dot
            dot_points.append(
                (
                    px(works),
                    py(avg),
                    studio,
                    avg,
                    rated,
                    dot,
                )
            )
            gesture = ft.GestureDetector(
                on_long_press_start=(
                    lambda event, d=dot, s=studio, a=avg, r=rated: (
                        show_dot(d, s, a, r)
                    )
                ),
                on_long_press_move_update=(
                    lambda event, x=px(works), y=py(avg): long_move(
                        event,
                        x,
                        y,
                    )
                ),
                on_long_press_end=lambda event: hide_dot(),
                on_long_press_cancel=lambda event: hide_dot(),
                content=dot,
            )
            controls.append(gesture)
            dot_controls.append(dot)

        controls.extend(
            [
                ft.Container(
                    left=left,
                    top=top - 44,
                    content=ui_text(
                        "平均分", size=11, color=secondary
                    ),
                ),
                ft.Container(
                    left=chart_width - right - 60,
                    top=top + plot_h + 30,
                    width=60,
                    alignment=ft.Alignment.CENTER_RIGHT,
                    content=ui_text(
                        "作品数", size=11, color=secondary
                    ),
                ),
                ft.Container(
                    left=left,
                    top=top - 22,
                    content=ui_text(
                        "低产高质（精致）",
                        size=11,
                        color=secondary,
                    ),
                ),
                ft.Container(
                    left=chart_width - right - 160,
                    top=top - 22,
                    width=160,
                    alignment=ft.Alignment.CENTER_RIGHT,
                    content=ui_text(
                        "高产高质（实力）",
                        size=11,
                        color=secondary,
                    ),
                ),
                ft.Container(
                    left=left,
                    top=top + plot_h + 10,
                    content=ui_text(
                        "低产低质", size=11, color=secondary
                    ),
                ),
                ft.Container(
                    left=chart_width - right - 80,
                    top=top + plot_h + 10,
                    width=80,
                    alignment=ft.Alignment.CENTER_RIGHT,
                    content=ui_text(
                        "高产低质", size=11, color=secondary
                    ),
                ),
                info_label,
            ]
        )
        stack = ft.Stack(
            width=chart_width,
            height=height,
            controls=controls,
        )
        chart_body: ft.Control = stack
        if chart_width > available:
            chart_body = ft.Row(
                scroll=ft.Scrollbar(
                    orientation=ft.ScrollbarOrientation.BOTTOM,
                    thumb_visibility=True,
                    track_visibility=True,
                ),
                controls=[stack],
            )
        note = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ui_text(
                    "无评分的动画不参与统计",
                    size=11,
                    color=ft.Colors.with_opacity(0.55, fg),
                )
            ],
        )
        return _back_view(
            page,
            route=route,
            title="制作公司 —— 质量 × 产量",
            controls=[vertical_page([chart_body, note])],
        )

    state: dict[str, ft.View | None] = {"view": None}
    state["view"] = build_view()
    if animate:
        page.run_task(
            animate_heat_cells,
            page,
            dot_controls,
            seconds=ANIMATION_SECONDS,
        )
    state["view"].data = {
        "rebuild": lambda: studio_scatter_view(page)
    }
    previous_resize = page.on_resize

    def on_resize(event: ft.ControlEvent) -> None:
        current = state["view"]
        if current is not None and current in page.views:
            if page.views[-1] is current:
                index = page.views.index(current)
                new_view = build_view(entry_animation=False)
                page.views[index] = new_view
                state["view"] = new_view
                try:
                    page.update()
                except RuntimeError:
                    return
        if (
            previous_resize is not None
            and previous_resize is not on_resize
        ):
            previous_resize(event)

    page.on_resize = on_resize
    return state["view"]
