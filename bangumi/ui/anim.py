"""条目动画共用的辅助函数。

约定：条目动画必须检查 ``entry_animations_enabled()``；
其他动画必须用 ``animation()`` / ``duration()`` 构建。
"""

from __future__ import annotations

import asyncio

import flet as ft

from bangumi.ui.interaction import is_attached

MODE_LABELS = {
    "full": "显示全部动画",
    "off": "不显示入场动画",
}

_cached_mode: str | None = None


def animation_mode() -> str:
    global _cached_mode
    if _cached_mode is None:
        from bangumi.data.preferences import Preferences

        mode = Preferences.load().animation_mode
        _cached_mode = mode if mode in MODE_LABELS else "full"
    return _cached_mode


def set_animation_mode(mode: str) -> None:
    global _cached_mode
    _cached_mode = mode if mode in MODE_LABELS else "full"


def entry_animations_enabled() -> bool:
    return animation_mode() == "full"


def animations_enabled() -> bool:
    return animation_mode() == "full"


def animation(
    ms: int,
    curve: ft.AnimationCurve = ft.AnimationCurve.EASE_OUT,
):
    return ft.Animation(ms, curve) if animations_enabled() else None


def duration(ms: int) -> int:
    return ms if animations_enabled() else 0


async def wait_until_ready(
    page: ft.Page,
    control: ft.Control | None,
    *,
    delay: float = 0.30,
) -> bool:
    """等待 ``control`` 挂载后，让首帧完成渲染。"""
    if control is None:
        return False
    for _ in range(50):
        await asyncio.sleep(0.02)
        if is_attached(control):
            break
    else:
        return False
    await asyncio.sleep(delay)
    return True
