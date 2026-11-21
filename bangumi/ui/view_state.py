"""按 View 实例保存页面可变 UI 状态。"""

from __future__ import annotations

from typing import Any

_STATES: dict[int, tuple[object, dict[str, Any]]] = {}


def state_for(view: object) -> dict[str, Any]:
    """返回视图对应的状态字典；首次访问时创建空字典。"""
    key = id(view)
    entry = _STATES.get(key)
    if entry is not None and entry[0] is view:
        return entry[1]
    state: dict[str, Any] = {}
    _STATES[key] = (view, state)
    return state


def forget(view: object) -> None:
    """视图被移出栈时丢弃其状态。"""
    entry = _STATES.get(id(view))
    if entry is not None and entry[0] is view:
        _STATES.pop(id(view), None)
