"""已阅页面的跨刷新状态（按 View 实例保存）。"""

from __future__ import annotations

from dataclasses import dataclass

from bangumi.ui.view_state import state_for


@dataclass
class WatchedViewState:
    """仅在应用运行期间保留的浏览状态。"""

    current_page: int = 0
    horizontal_offset: float = 0.0
    horizontal_max_extent: float = 0.0
    vertical_offset: float = 0.0
    vertical_owner: str = "page"
    vertical_max_extent: float = 0.0


def bind_view_state(view: object, state: WatchedViewState) -> None:
    """把浏览状态绑定到已阅页 View。"""
    state_for(view)["watched"] = state


def view_state(view: object) -> WatchedViewState:
    """读取视图对应的已阅状态；不存在时创建默认值。"""
    data = state_for(view)
    state = data.get("watched")
    if not isinstance(state, WatchedViewState):
        state = WatchedViewState()
        data["watched"] = state
    return state
