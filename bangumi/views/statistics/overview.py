"""统计总览页。"""

from __future__ import annotations

import asyncio
import flet as ft
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.colors import (
    foreground_color,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.ui.anim import (
    entry_animations_enabled,
    wait_until_ready,
)
from bangumi.ui.page_state import first_entry, mark_seen
from bangumi.data.statistics.models import DetailItem
from bangumi.data.statistics.overview import overview_data
from bangumi.data.sorting import sort_detail_items
from bangumi.views.templates.list_page import open_list_page
from bangumi.views.statistics.common.overlays import (
    _PanelOverlay,
    _attach_overlay_cleanup,
    _install_overlay_hook,
    _register_overlay,
    _ring_block,
)
from bangumi.views.statistics.common.shared import (
    ANIMATION_SECONDS,
    ANIMATION_STEPS,
    CARD_HEIGHT,
    _CARD_COLORS,
    _CATEGORY_COLORS,
    _SEGMENT_COLORS,
    _accent,
    _segmented_ring,
    _single_ring,
    _type_chip,
)
from bangumi.views.widgets.stat_card import stat_card


def overview_view(page: ft.Page) -> ft.View:
    play_animation = entry_animations_enabled() and first_entry(
        page, "/statistics/overview"
    )
    if play_animation:
        mark_seen(page, "/statistics/overview")
    data = overview_data()
    accent_colors = [
        _accent(page, light, dark) for light, dark in _CARD_COLORS
    ]
    segment_colors = {
        name: _accent(page, light, dark)
        for name, light, dark in _SEGMENT_COLORS
    }
    category_colors = {
        name: _accent(page, light, dark)
        for name, (light, dark) in _CATEGORY_COLORS.items()
    }
    animated: list[tuple[ft.Text, int]] = []
    rings: list[tuple[ft.ProgressRing, float]] = []
    text_color = foreground_color(page)
    overlay = _PanelOverlay(page)
    _register_overlay(page, overlay)
    _install_overlay_hook(page)

    def card(
        index: int,
        *,
        title: str,
        numbers: tuple[tuple[int, str], ...],
        detail_title: str,
        slug: str,
        items: list[DetailItem],
    ) -> ft.Control:
        accent = accent_colors[index]

        def on_click(event: ft.ControlEvent) -> None:
            open_list_page(
                page,
                title=detail_title,
                route=f"/statistics/overview/{slug}",
                entries=sort_detail_items(items),
                records=data.records,
            )

        return stat_card(
            page,
            title,
            numbers,
            accent=accent,
            expand=None,
            clickable=True,
            on_click=on_click,
            compact=True,
            layout="numbers",
            animated=animated,
            height=CARD_HEIGHT,
        )

    chips = ft.Row(
        spacing=8,
        controls=[
            _type_chip(
                page,
                label="OVA",
                count=data.ova_count,
                color=segment_colors["OVA"],
                on_click=(
                    lambda event, items=data.ova_items: open_list_page(
                        page,
                        title="OVA明细",
                        route="/statistics/overview/ova",
                        entries=sort_detail_items(items),
                        records=data.records,
                    )
                ),
            ),
            _type_chip(
                page,
                label="OAD",
                count=data.oad_count,
                color=segment_colors["OAD"],
                on_click=(
                    lambda event, items=data.oad_items: open_list_page(
                        page,
                        title="OAD明细",
                        route="/statistics/overview/oad",
                        entries=sort_detail_items(items),
                        records=data.records,
                    )
                ),
            ),
            _type_chip(
                page,
                label="SP",
                count=data.sp_count,
                color=segment_colors["SP"],
                on_click=(
                    lambda event, items=data.sp_items: open_list_page(
                        page,
                        title="SP明细",
                        route="/statistics/overview/sp",
                        entries=sort_detail_items(items),
                        records=data.records,
                    )
                ),
            ),
        ],
    )

    cards = [
        card(
            0,
            title="总条数",
            numbers=((data.entries, "条"),),
            detail_title="总条数明细",
            slug="total",
            items=data.total_items,
        ),
        card(
            1,
            title="动画数",
            numbers=((data.anime_count, "部"),),
            detail_title="动画数明细",
            slug="entries",
            items=data.anime_items,
        ),
        card(
            2,
            title="TV",
            numbers=(
                (data.tv_count, "部"),
                (data.tv_episodes, "话"),
            ),
            detail_title="TV明细",
            slug="tv",
            items=data.tv_items,
        ),
        chips,
        card(
            3,
            title="电影 / 剧场版",
            numbers=(
                (data.movie_count, "部"),
                (data.movie_minutes, "分钟"),
            ),
            detail_title="电影明细",
            slug="movie",
            items=data.movie_items,
        ),
        card(
            4,
            title="已公开续作",
            numbers=((data.sequel_count, "部"),),
            detail_title="续作明细",
            slug="sequel",
            items=data.sequel_items,
        ),
    ]

    segments = (
        ("TV", data.tv_count, segment_colors["TV"]),
        ("OVA", data.ova_count, segment_colors["OVA"]),
        ("OAD", data.oad_count, segment_colors["OAD"]),
        ("SP", data.sp_count, segment_colors["SP"]),
        ("电影", data.feature_count, segment_colors["电影"]),
        ("剧场版", data.theater_count, segment_colors["剧场版"]),
    )
    multi_ring = _segmented_ring(page, segments=segments, rings=rings)
    multi_block = _ring_block(
        page,
        title="规格分布",
        ring=multi_ring,
        accent=accent_colors[0],
        col={"xs": 12, "sm": 4},
        panel_title=f"总条数 {data.total}",
        panel_rows=list(segments),
        overlay=overlay,
    )

    category_segments = tuple(
        (
            name,
            count,
            category_colors.get(
                name,
                category_colors["其他"],
            ),
        )
        for name, count in data.category_counts
    )
    category_ring = _segmented_ring(
        page,
        segments=category_segments,
        rings=rings,
    )
    category_block = _ring_block(
        page,
        title="类型分布",
        ring=category_ring,
        accent=accent_colors[0],
        col={"xs": 12, "sm": 4},
        panel_title=f"总条数 {data.total}",
        panel_rows=list(category_segments),
        overlay=overlay,
    )

    sequel_ratio = (
        data.sequel_count / data.entries if data.entries else 0.0
    )
    sequel_ring = _single_ring(
        page,
        ratio=sequel_ratio,
        color=accent_colors[4],
        rings=rings,
    )
    sequel_block = _ring_block(
        page,
        title="续作占比",
        ring=sequel_ring,
        accent=accent_colors[4],
        col={"xs": 12, "sm": 4},
        panel_title=f"动画数 {data.entries}",
        panel_rows=[
            ("续作", data.sequel_count, accent_colors[4]),
            (
                "其它",
                data.entries - data.sequel_count,
                ft.Colors.with_opacity(0.35, text_color),
            ),
        ],
        overlay=overlay,
    )

    ring_row = ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[multi_block, category_block, sequel_block],
    )

    view = ft.View(
        route="/statistics/overview",
        appbar=ft.AppBar(title=ui_text("总览")),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.Column(
                        spacing=8,
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.STRETCH
                        ),
                        controls=cards,
                    ),
                    ft.Container(height=2),
                    ring_row,
                ],
                spacing=8,
            )
        ],
    )
    view.data = {
        "rebuild": lambda: overview_view(page)
    }
    _attach_overlay_cleanup(view, overlay)

    animation_controls = [text for text, _ in animated] + [
        ring for ring, _ in rings
    ]

    async def animate() -> None:
        if not await wait_until_ready(page, ring_row):
            return
        for step in range(1, ANIMATION_STEPS + 1):
            if view not in page.views:
                return
            progress = step / ANIMATION_STEPS
            eased = 1 - (1 - progress) ** 3
            for text, target in animated:
                text.value = f"{round(target * eased):,}"
            for ring, ratio in rings:
                ring.value = ratio * eased
            page.update(*animation_controls)
            await asyncio.sleep(ANIMATION_SECONDS / ANIMATION_STEPS)

        if view not in page.views:
            return
        for text, target in animated:
            text.value = f"{target:,}"
        for ring, ratio in rings:
            ring.value = ratio
        page.update(*animation_controls)

    if play_animation:
        page.run_task(animate)
    else:
        for text, target in animated:
            text.value = f"{target:,}"
        for ring, ratio in rings:
            ring.value = ratio
    return view


