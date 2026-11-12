"""已阅页面的跨刷新状态。"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft


@dataclass
class WatchedViewState:
    """仅在应用运行期间保留的浏览状态。"""

    current_page: int = 0
    horizontal_offset: float = 0.0
    vertical_offset: float = 0.0
VIEW_STATES: dict[int, tuple[ft.Page, WatchedViewState]] = {}
def view_state(page: ft.Page) -> WatchedViewState:
    key = id(page)
    entry = VIEW_STATES.get(key)
    if entry is not None and entry[0] is page:
        return entry[1]

    state = WatchedViewState()
    VIEW_STATES[key] = (page, state)
    return state
