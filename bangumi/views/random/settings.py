"""随机设置页。"""

from __future__ import annotations

import copy
from datetime import date

import flet as ft

from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import back_icon
from bangumi.ui.layout import page_padding
from bangumi.ui.theme import ui_text
from bangumi.views.random.state import (
    PRESETS,
    RandomParams,
    get_state,
)
from bangumi.views.navigation import go_back, push_view

_EDITING: dict[int, object] = {}

TYPE_GROUPS = [
    ("TV", ["tv"]),
    ("电影", ["movie"]),
    ("OVA", ["ova"]),
    ("SP", ["special", "tv_special"]),
    ("其它", ["ona", "music", "cm", "pv"]),
]
STATUS_GROUPS = [
    ("已完结", ["complete"]),
    ("放送中", ["airing"]),
    ("未放送", ["upcoming"]),
]
RATING_GROUPS = [
    ("全年龄", ["g"]),
    ("PG", ["pg"]),
    ("PG-13", ["pg13"]),
    ("限制级", ["r17"]),
    ("R", ["r"]),
    ("绅士", ["rx"]),
]
SOURCE_GROUPS = [
    ("原创", ["original"]),
    (
        "漫画",
        ["manga", "4_koma_manga", "web_manga", "digital_manga"],
    ),
    ("小说", ["novel", "web_novel", "light_novel"]),
    ("视觉小说", ["visual_novel"]),
    ("游戏", ["game", "card_game"]),
    (
        "其它",
        [
            "book",
            "picture_book",
            "radio",
            "music",
            "mixed_media",
            "other",
            "unknown",
        ],
    ),
]
VOICE_GROUPS = [
    ("日语", ["japanese"]),
    ("英语", ["english"]),
    ("韩语", ["korean"]),
    (
        "其它",
        [
            "french",
            "german",
            "hebrew",
            "hungarian",
            "italian",
            "mandarin",
            "portuguese_br",
            "spanish",
        ],
    ),
]
SEASON_GROUPS = [
    ("冬", ["winter"]),
    ("春", ["spring"]),
    ("夏", ["summer"]),
    ("秋", ["fall"]),
]


def _multi_select(
    page: ft.Page,
    groups: list[tuple[str, list[str]]],
    initial: list[str],
    reset=None,
):
    """自定义多选下拉：点击选项只切换状态，面板保持展开。"""
    chosen = {
        text
        for text, values in groups
        if any(value in initial for value in values)
    }
    label = ft.Text(
        "、".join(text for text, _ in groups if text in chosen)
        or "可多选",
        size=12,
        color=foreground_color(page),
    )
    panel: dict[str, ft.Container | None] = {"value": None}

    def update_label() -> None:
        label.value = (
            "、".join(text for text, _ in groups if text in chosen)
            or "可多选"
        )
        try:
            label.update()
        except Exception:
            pass

    def rebuild() -> None:
        box = panel["value"]
        if box is None:
            return
        rows: list[ft.Control] = []
        for text, _ in groups:
            tick = ft.Icon(
                ft.Icons.CHECK,
                size=16,
                visible=text in chosen,
            )
            rows.append(
                ft.Container(
                    height=36,
                    on_click=lambda e, t=text: toggle(t),
                    content=ft.Row(
                        spacing=4,
                        controls=[
                            ft.Container(width=24, content=tick),
                            ui_text(text, size=13),
                        ],
                    ),
                )
            )
        box.content.controls = rows
        try:
            box.update()
        except Exception:
            pass

    def toggle(text: str) -> None:
        if text in chosen:
            chosen.remove(text)
        else:
            chosen.add(text)
        update_label()
        rebuild()
        if callable(reset):
            reset()

    def toggle_panel(event=None) -> None:
        box = panel["value"]
        if box is None:
            return
        box.visible = not box.visible
        rebuild()
        try:
            box.update()
        except Exception:
            pass

    trigger = ft.Container(
        border=ft.Border.all(1, "#E5E8EE"),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        on_click=toggle_panel,
        content=label,
    )
    box = ft.Container(
        visible=False,
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#E5E8EE"),
        border_radius=8,
        padding=ft.Padding.all(6),
        content=ft.Column(spacing=0, controls=[]),
    )
    panel["value"] = box
    rebuild()
    wrapper = ft.Column(spacing=4, controls=[trigger, box])

    def set_values(new_values: list[str]) -> None:
        chosen.clear()
        for text, vals in groups:
            if any(value in new_values for value in vals):
                chosen.add(text)
        update_label()
        rebuild()

    def values() -> list[str]:
        result: list[str] = []
        for text, vals in groups:
            if text not in chosen:
                continue
            for value in vals:
                if value not in result:
                    result.append(value)
        return result

    return wrapper, values, set_values


def _single_select(
    page: ft.Page,
    options: list[str],
    current: str,
    on_pick,
):
    """自定义单选下拉：白底面板 + 勾选，选中后关闭面板。"""
    state = {"value": current or "无"}
    label = ft.Text(
        state["value"],
        size=12,
        color=foreground_color(page),
    )
    panel = ft.Container(
        visible=False,
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#E5E8EE"),
        border_radius=8,
        padding=ft.Padding.all(6),
        content=ft.Column(spacing=0, controls=[]),
    )

    def rebuild() -> None:
        rows: list[ft.Control] = []
        for name in options:
            tick = ft.Icon(
                ft.Icons.CHECK,
                size=16,
                visible=name == state["value"],
            )
            rows.append(
                ft.Container(
                    height=36,
                    on_click=lambda e, n=name: pick(n),
                    content=ft.Row(
                        spacing=4,
                        controls=[
                            ft.Container(width=24, content=tick),
                            ui_text(name, size=13),
                        ],
                    ),
                )
            )
        panel.content.controls = rows
        try:
            panel.update()
        except Exception:
            pass

    def pick(name: str) -> None:
        state["value"] = name
        label.value = name
        try:
            label.update()
        except Exception:
            pass
        panel.visible = False
        rebuild()
        on_pick(name)

    def toggle(event=None) -> None:
        panel.visible = not panel.visible
        rebuild()
        try:
            panel.update()
        except Exception:
            pass

    trigger = ft.Container(
        border=ft.Border.all(1, "#E5E8EE"),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        on_click=toggle,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                label,
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18),
            ],
        ),
    )
    rebuild()
    wrapper = ft.Column(spacing=4, controls=[trigger, panel])

    def set_value(name: str) -> None:
        state["value"] = name
        label.value = name
        try:
            label.update()
        except Exception:
            pass
        rebuild()

    return wrapper, set_value


def build_random_settings_view(page: ft.Page) -> ft.View:
    source = get_state(page)
    # 编辑副本，确认时才写回；预设切换时复用同一份。
    params = _EDITING.get(id(page))
    if params is None:
        params = copy.deepcopy(source)
    _EDITING[id(page)] = params
    fg = foreground_color(page)
    current_year = date.today().year

    def row(label: str, control: ft.Control, full: bool = False) -> ft.Control:
        head = ui_text(
            label,
            size=13,
            weight=ft.FontWeight.BOLD,
            color=fg,
        )
        if full:
            return ft.Column(spacing=4, controls=[head, control])
        return ft.Column(
            spacing=4,
            controls=[head, ft.Row([control])],
        )

    applying = {"value": False}

    def clear_preset() -> None:
        if applying["value"]:
            return
        if params.preset != "无":
            params.preset = "无"
            try:
                preset_set("无")
            except Exception:
                pass

    preset, preset_set = _single_select(
        page,
        list(PRESETS),
        params.preset,
        lambda name: apply_preset(name),
    )

    q_field = ft.TextField(
        value=params.q,
        hint_text="可为空，搜中文名没用",
        text_size=14,
        border_radius=8,
        expand=True,
        on_change=lambda e: clear_preset(),
    )
    type_ctl, type_get, type_set = _multi_select(
        page, TYPE_GROUPS, params.type, clear_preset
    )
    status_ctl, status_get, status_set = _multi_select(
        page, STATUS_GROUPS, params.status, clear_preset
    )
    rating_ctl, rating_get, rating_set = _multi_select(
        page, RATING_GROUPS, params.rating, clear_preset
    )
    source_ctl, source_get, source_set = _multi_select(
        page, SOURCE_GROUPS, params.source, clear_preset
    )
    voice_ctl, voice_get, voice_set = _multi_select(
        page, VOICE_GROUPS, params.voice_language, clear_preset
    )
    season_ctl, season_get, season_set = _multi_select(
        page, SEASON_GROUPS, params.season, clear_preset
    )

    score_clamp_state = {"busy": False}

    def clamp_score(start: float, end: float) -> tuple[float, float]:
        start = round(float(start), 2)
        end = round(float(end), 2)
        if end < 1.0:
            end = 1.0
        if start > end:
            start = end
        return start, end

    score_text = ui_text(
        f"{params.min_score:.2f} ~ {params.max_score:.2f}",
        size=12,
        color=fg,
    )

    def on_score_change(event) -> None:
        if score_clamp_state["busy"]:
            return
        clear_preset()
        control = event.control
        start, end = clamp_score(
            control.start_value, control.end_value
        )
        score_text.value = f"{start:.2f} ~ {end:.2f}"
        try:
            score_text.update()
        except Exception:
            pass
        changed = (
            abs(float(control.start_value) - start) > 1e-9
            or abs(float(control.end_value) - end) > 1e-9
        )
        if not changed:
            return
        score_clamp_state["busy"] = True
        try:
            control.start_value = start
            control.end_value = end
            control.update()
        finally:
            score_clamp_state["busy"] = False

    score_slider = ft.RangeSlider(
        min=0,
        max=10,
        start_value=params.min_score,
        end_value=params.max_score,
        on_change=on_score_change,
    )

    member_cap = 5_000_000
    members_text = ui_text(
        (
            f"{params.min_members} ~ ∞"
            if params.max_members >= 2000000000
            else f"{params.min_members} ~ {params.max_members}"
        ),
        size=12,
        color=fg,
    )
    members_slider = ft.RangeSlider(
        min=0,
        max=member_cap,
        start_value=min(params.min_members, member_cap),
        end_value=min(params.max_members, member_cap),
        on_change=lambda e: (
            clear_preset(),
            setattr(
                members_text,
                "value",
                (
                    f"{int(e.control.start_value)} ~ ∞"
                    if e.control.end_value >= member_cap
                    else f"{int(e.control.start_value)}"
                    f" ~ {int(e.control.end_value)}"
                ),
            ),
            members_text.update(),
        ),
    )

    year_text = ui_text(
        (
            f"{1 if params.min_year <= 1930 else params.min_year}"
            f" ~ {params.max_year}"
        ),
        size=12,
        color=fg,
    )
    year_slider = ft.RangeSlider(
        min=1930,
        max=current_year,
        start_value=max(1930, min(params.min_year, current_year)),
        end_value=max(1930, min(params.max_year, current_year)),
        on_change=lambda e: (
            clear_preset(),
            setattr(
                year_text,
                "value",
                (
                    f"{1 if int(e.control.start_value) <= 1930 else int(e.control.start_value)}"
                    f" ~ {int(e.control.end_value)}"
                ),
            ),
            year_text.update(),
        ),
    )

    def apply_preset(name: str) -> None:
        fresh = RandomParams()
        for key, value in PRESETS.get(name, {}).items():
            setattr(fresh, key, value)
        fresh.preset = name
        applying["value"] = True
        try:
            for key in (
                "q",
                "type",
                "status",
                "rating",
                "source",
                "voice_language",
                "min_score",
                "max_score",
                "min_members",
                "max_members",
                "min_year",
                "max_year",
                "season",
                "preset",
            ):
                setattr(params, key, getattr(fresh, key))
            q_field.value = fresh.q
            type_set(fresh.type)
            status_set(fresh.status)
            rating_set(fresh.rating)
            source_set(fresh.source)
            voice_set(fresh.voice_language)
            season_set(fresh.season)
            score_slider.start_value = fresh.min_score
            score_slider.end_value = fresh.max_score
            score_text.value = (
                f"{fresh.min_score:.2f} ~ {fresh.max_score:.2f}"
            )
            members_start = min(fresh.min_members, member_cap)
            members_end = min(fresh.max_members, member_cap)
            members_slider.start_value = members_start
            members_slider.end_value = members_end
            members_text.value = (
                f"{members_start} ~ ∞"
                if members_end >= member_cap
                else f"{members_start} ~ {members_end}"
            )
            year_start = max(1930, min(fresh.min_year, current_year))
            year_end = max(1930, min(fresh.max_year, current_year))
            year_slider.start_value = year_start
            year_slider.end_value = year_end
            year_text.value = (
                f"{1 if year_start <= 1930 else year_start}"
                f" ~ {year_end}"
            )
            for control in (
                q_field,
                score_slider,
                members_slider,
                year_slider,
                score_text,
                members_text,
                year_text,
            ):
                try:
                    control.update()
                except Exception:
                    pass
        finally:
            applying["value"] = False

    def confirm(event=None) -> None:
        params.q = str(q_field.value or "").strip()
        params.type = type_get()
        params.status = status_get()
        params.rating = rating_get()
        params.source = source_get()
        params.voice_language = voice_get()
        params.season = season_get()
        score_start, score_end = clamp_score(
            score_slider.start_value,
            score_slider.end_value,
        )
        params.min_score = score_start
        params.max_score = score_end
        params.min_members = int(members_slider.start_value)
        params.max_members = (
            2000000000
            if members_slider.end_value >= member_cap
            else int(members_slider.end_value)
        )
        low_year = int(year_slider.start_value)
        params.min_year = 1 if low_year <= 1930 else low_year
        params.max_year = int(year_slider.end_value)
        # 确认后才写回页面级参数。
        for name in (
            "q",
            "type",
            "status",
            "rating",
            "source",
            "voice_language",
            "min_score",
            "max_score",
            "min_members",
            "max_members",
            "min_year",
            "max_year",
            "season",
        ):
            setattr(source, name, getattr(params, name))
        source.params_dirty = True
        source.suppress_auto_settings = True
        _EDITING.pop(id(page), None)
        from bangumi.views.navigation import go_back

        go_back(page, "/random/settings")

    rows: list[ft.Control] = [
        row("预设", preset),
        row("关键词", q_field, full=True),
        row("类型", type_ctl),
        row("状态", status_ctl),
        row("分级", rating_ctl),
        row("来源", source_ctl),
        row("配音", voice_ctl),
        row("评分", ft.Column([score_slider, score_text]), full=True),
        row("人气", ft.Column([members_slider, members_text]), full=True),
        row("年份", ft.Column([year_slider, year_text]), full=True),
        row("季度", season_ctl),
        ft.Row(
            alignment=ft.MainAxisAlignment.END,
            controls=[
                ft.Button(
                    content=ui_text("确认", color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.GREEN,
                    on_click=confirm,
                )
            ],
        ),
    ]

    def mark_cancel() -> None:
        # 未确认返回：丢弃编辑副本，不写参数。
        _EDITING.pop(id(page), None)
        get_state(page).suppress_auto_settings = True

    view = ft.View(
        route="/random/settings",
        appbar=ft.AppBar(
            title=ui_text("随机（设置）"),
            automatically_imply_leading=False,
            leading=back_icon(
                page,
                "/random",
                before=mark_cancel,
            ),
        ),
        padding=page_padding(),
        controls=[
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=rows,
            )
        ],
    )
    return view


def open_random_settings(page: ft.Page) -> None:
    push_view(page, build_random_settings_view(page))
