"""用于重排观影表格列的可拖动表头。"""

from __future__ import annotations

from typing import Callable

import flet as ft

from bangumi.ui.theme import stats_text
from bangumi.ui.colors import (
    foreground_color,
)

DRAG_GROUP = "watched-columns"
HEADER_HEIGHT = 32
FLOATING_LABEL_SIZE = 21

MoveColumn = Callable[[str | None, str, bool], None]


class DraggableHeader:
    """可拖到另一个表头上的列标题。"""

    def __init__(
        self,
        page: ft.Page,
        *,
        key: str,
        label: str,
        width: int,
        floating_width: int,
        anchor_positions: dict[str, float],
        move_column: MoveColumn,
    ) -> None:
        self.page = page
        self.key = key
        self.label = label
        self.width = width
        self.floating_width = floating_width
        self.anchor_positions = anchor_positions
        self.move_column = move_column
        self.feedback_label = self._build_feedback_label()

    def control(self) -> ft.Control:
        return ft.DragTarget(
            group=DRAG_GROUP,
            on_accept=self._accept_drop,
            content=ft.Draggable(
                group=DRAG_GROUP,
                axis=ft.Axis.HORIZONTAL,
                affinity=ft.Axis.HORIZONTAL,
                data=self.key,
                content=ft.GestureDetector(
                    on_enter=self._track_anchor,
                    on_hover=self._track_anchor,
                    hover_interval=30,
                    content=ft.Container(
                        width=self.width,
                        height=HEADER_HEIGHT,
                        alignment=ft.Alignment.CENTER,
                        content=self._heading_text(),
                    ),
                ),
                content_feedback=ft.Stack(
                    width=self.width,
                    height=HEADER_HEIGHT,
                    clip_behavior=ft.ClipBehavior.NONE,
                    controls=[self.feedback_label],
                ),
            ),
        )

    def _heading_text(self) -> ft.Text:
        return stats_text(
            self.label,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
            no_wrap=True,
        )

    def _build_feedback_label(self) -> ft.Container:
        anchor_x = self.anchor_positions.get(self.key, self.width / 2)
        return ft.Container(
            left=anchor_x - self.floating_width / 2,
            top=0,
            width=self.floating_width,
            height=HEADER_HEIGHT,
            alignment=ft.Alignment.CENTER,
            # 拖拽反馈渲染在根 Overlay 中，位于
            # Material 树之外。把文本包进不可见的 Card 可提供
            # Material 宿主，并避免 Flutter 的回退样式
            #（红色文字加黄色下划线）。
            content=ft.Card(
                elevation=0,
                margin=ft.Margin.all(0),
                bgcolor=ft.Colors.TRANSPARENT,
                shadow_color=ft.Colors.TRANSPARENT,
                content=stats_text(
                    self.label,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                    no_wrap=True,
                    size=FLOATING_LABEL_SIZE,
                    color=foreground_color(self.page),
                ),
            ),
        )

    def _track_anchor(self, event: ft.HoverEvent) -> None:
        position = getattr(event, "local_position", None)
        if position is None:
            return

        x = float(position.x)
        self.anchor_positions[self.key] = x
        left = x - self.floating_width / 2
        if (
            self.feedback_label.left is not None
            and abs(self.feedback_label.left - left) < 1
        ):
            return

        self.feedback_label.left = left
        try:
            self.feedback_label.update()
        except RuntimeError:
            # 拖拽开始前，反馈不会被挂载。
            pass

    def _accept_drop(self, event: ft.DragTargetEvent) -> None:
        source_key = self._source_key(event)
        position = getattr(event, "local_position", None)
        if position is None:
            pointer_x = self.width / 2
        else:
            # Flutter 报告的是反馈的左上角，而非指针位置。
            anchor = self.anchor_positions.get(
                source_key or "",
                self.width / 2,
            )
            pointer_x = position.x + anchor

        self.move_column(
            source_key,
            self.key,
            pointer_x > self.width / 2,
        )

    def _source_key(self, event: ft.DragTargetEvent) -> str | None:
        if event.src_id is None:
            return None
        try:
            control = self.page.get_control(event.src_id)
        except Exception:
            return None
        if isinstance(control, ft.Draggable):
            return control.data
        return None
