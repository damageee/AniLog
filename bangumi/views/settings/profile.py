"""设置页头像、名字与彩蛋气泡。"""

from __future__ import annotations

import time

import flet as ft
from bangumi.ui.anim import animation
from bangumi.ui.events import is_hover

from bangumi.ui.colors import foreground_color
from bangumi.ui.interaction import tooltip_colors
from bangumi.ui.constants import ANIM_SLOW_MS
from bangumi.ui.platform import is_mobile
from bangumi.ui.text_metrics import text_width
from bangumi.ui.theme import ui_text

PROFILE_IMAGE_SIZE = 120
PROFILE_NAME_SIZE = 40

_EGG_STATES: dict[int, dict] = {}


def build_profile_block(page: ft.Page) -> ft.Control:
    fg = foreground_color(page)
    bg, tip_fg = tooltip_colors(page)
    mobile = is_mobile(page)

    image_holder = ft.Container(
        width=PROFILE_IMAGE_SIZE,
        height=PROFILE_IMAGE_SIZE,
        content=ft.Image(
            src="/pic/head.jpg",
            width=PROFILE_IMAGE_SIZE,
            height=PROFILE_IMAGE_SIZE,
            fit=ft.BoxFit.CONTAIN,
        ),
    )

    avatar_stack = ft.Container(
        width=PROFILE_IMAGE_SIZE + 64,
        height=PROFILE_IMAGE_SIZE,
        alignment=ft.Alignment.CENTER,
        content=image_holder,
    )

    BUBBLE_TEXT = "这是我老婆，不用跳高了"
    BUBBLE_SIZE = 13
    BUBBLE_PAD_X = 12
    BUBBLE_PAD_Y = 6
    BUBBLE_TAIL = 10
    NAME_TEXT = "Made by damage"

    name_size = PROFILE_NAME_SIZE
    name_px = text_width(NAME_TEXT, size=name_size)
    line_w = name_px + max(24, int(name_px * 0.08))
    available = max(80.0, float(page.width or 1000) - 48)
    bubble_text_w = text_width(BUBBLE_TEXT, size=BUBBLE_SIZE)
    bubble_w = bubble_text_w + BUBBLE_PAD_X * 2 + 24
    bubble_h = max(
        int(BUBBLE_SIZE * 2.2) + BUBBLE_PAD_Y * 2,
        40,
    )
    narrow = max(line_w, bubble_w) > available * 0.92

    # 窄屏替代文字的字号：让整行刚好放进 available
    w_at_name = max(1.0, text_width(BUBBLE_TEXT, size=name_size))
    fit_size = max(
        12,
        int(name_size * available * 0.90 / w_at_name),
    )
    fit_size = min(fit_size, name_size)
    w_name = max(1.0, text_width(NAME_TEXT, size=name_size))
    name_fit_size = max(
        12,
        int(name_size * available * 0.92 / w_name),
    )
    name_fit_size = min(name_fit_size, name_size)

    name_text = ui_text(
        NAME_TEXT,
        size=name_size,
        no_wrap=True,
        max_lines=1,
        text_align=ft.TextAlign.CENTER,
    )
    name_text.animate_opacity = animation(
        ANIM_SLOW_MS, ft.AnimationCurve.EASE_OUT
    )
    name_text.opacity = 1.0

    replacement = ui_text(
        BUBBLE_TEXT,
        size=fit_size,
        no_wrap=True,
        max_lines=1,
        text_align=ft.TextAlign.CENTER,
    )
    replacement.animate_opacity = animation(
        ANIM_SLOW_MS, ft.AnimationCurve.EASE_OUT
    )
    replacement.opacity = 0.0

    if narrow:
        name_text.size = name_fit_size
        name_area = ft.Stack(
            width=available,
            height=max(name_size, fit_size) * 1.4,
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[name_text, replacement],
        )
        bubble_box = None
    else:
        bubble_body = ft.Container(
            padding=ft.Padding.symmetric(
                horizontal=BUBBLE_PAD_X,
                vertical=BUBBLE_PAD_Y,
            ),
            border_radius=4,
            bgcolor=bg,
            content=ui_text(
                BUBBLE_TEXT,
                size=BUBBLE_SIZE,
                color=tip_fg,
                no_wrap=True,
                max_lines=1,
                overflow=ft.TextOverflow.VISIBLE,
            ),
        )
        tail = ft.Container(
            width=BUBBLE_TAIL,
            height=BUBBLE_TAIL,
            bgcolor=bg,
            rotate=ft.Rotate(angle=0.785398),
            right=BUBBLE_TAIL + 16,
            bottom=-1,
        )
        bubble_box = ft.Stack(
            width=bubble_w,
            height=bubble_h,
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[bubble_body, tail],
        )
        bubble_box.opacity = 0.0
        bubble_box.animate_opacity = animation(
            ANIM_SLOW_MS, ft.AnimationCurve.EASE_OUT
        )
        bubble_box.ignore_interactions = True
        name_h = name_size * 1.4
        name_area = ft.Stack(
            width=line_w,
            height=name_h,
            controls=[name_text],
        )

    name_h = name_size * 1.4
    profile_column = ft.Column(
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[avatar_stack, name_area],
    )
    if narrow:
        profile_block = profile_column
    else:
        profile_w = max(
            line_w, PROFILE_IMAGE_SIZE + 64
        )
        name_left = (profile_w - line_w) / 2
        bubble_left = max(
            0.0,
            name_left + line_w - bubble_w,
        )
        bubble_holder = ft.Container(
            left=bubble_left,
            top=PROFILE_IMAGE_SIZE + 10 - bubble_h - 6,
            ignore_interactions=True,
            content=bubble_box,
        )
        profile_block = ft.Stack(
            width=profile_w,
            height=PROFILE_IMAGE_SIZE + 10 + name_h,
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[profile_column, bubble_holder],
        )

    shown = {"at": 0.0}
    egg_open = {"value": False}

    def set_egg(open_: bool) -> None:
        if egg_open["value"] == open_:
            return
        egg_open["value"] = open_
        shown["at"] = time.time()
        if narrow:
            name_text.opacity = 0.0 if open_ else 1.0
            replacement.opacity = 1.0 if open_ else 0.0
        elif bubble_box is not None:
            bubble_box.opacity = 1.0 if open_ else 0.0
        if narrow:
            changed_controls = [name_text, replacement]
        elif bubble_box is not None:
            changed_controls = [bubble_box]
        else:
            changed_controls = []
        if changed_controls:
            try:
                page.update(*changed_controls)
            except Exception:
                pass

    def on_image_hover(event):
        hovered = is_hover(event)
        set_egg(hovered)

    def on_image_click(event):
        set_egg(not egg_open["value"])

    if mobile:
        image_holder.on_click = on_image_click
    else:
        image_holder.on_hover = on_image_hover

    _EGG_STATES[id(page)] = {
        "shown": shown,
        "egg_open": egg_open,
        "set_egg": set_egg,
    }
    return profile_block


def handle_page_tap(page: ft.Page) -> None:
    state = _EGG_STATES.get(id(page))
    if state is None:
        return
    if (
        state["egg_open"]["value"]
        and time.time() - state["shown"]["at"] > 0.25
    ):
        state["set_egg"](False)
