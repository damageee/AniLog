"""热力图类控件共用的悬停/点击缩放辅助函数。"""

from __future__ import annotations

import asyncio
import math
import random

import flet as ft

from bangumi.ui.events import is_hover
from bangumi.ui.platform import is_desktop
from bangumi.ui.anim import animation, wait_until_ready

_ACTIVE: dict[int, ft.Container] = {}


def attach_heat_zoom(
    page: ft.Page,
    control: ft.Container,
    *,
    target: float = 1.2,
    duration: int = 160,
    on_tap=None,
    initial_scale: float = 1.0,
) -> ft.Container:
    control.scale = ft.Scale(initial_scale)
    control.animate_scale = animation(duration)

    def apply(on: bool) -> None:
        previous = _ACTIVE.get(id(page))
        if on and previous is not None and previous is not control:
            previous.scale = ft.Scale(1.0)
            try:
                previous.update()
            except Exception:
                pass
        if on:
            _ACTIVE[id(page)] = control
        elif _ACTIVE.get(id(page)) is control:
            _ACTIVE.pop(id(page), None)
        control.scale = ft.Scale(target if on else 1.0)
        try:
            control.update()
        except Exception:
            pass

    if is_desktop(page):
        control.on_hover = lambda event: apply(is_hover(event))
    else:
        def on_click(event: ft.ControlEvent) -> None:
            apply(True)
            if on_tap is not None:
                on_tap(event)

        control.on_click = on_click
    return control


def reset_heat_zoom(page: ft.Page) -> None:
    control = _ACTIVE.pop(id(page), None)
    if control is None:
        return
    control.scale = ft.Scale(1.0)
    try:
        control.update()
    except Exception:
        pass


async def animate_heat_cells(
    page: ft.Page,
    controls: list[ft.Container],
    *,
    batches: int = 36,
    seconds: float = 0.8,
) -> None:
    if not controls:
        return
    if not await wait_until_ready(page, controls[0]):
        return
    ordered = list(controls)
    random.shuffle(ordered)
    total = len(ordered)
    size = max(1, math.ceil(total / batches))
    for start in range(0, total, size):
        batch = ordered[start : start + size]
        for control in batch:
            control.opacity = 1
            control.scale = ft.Scale(1.0)
        try:
            page.update(*batch)
        except RuntimeError:
            return
        except Exception:
            pass
        await asyncio.sleep(seconds / batches)
