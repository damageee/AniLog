"""hover 状态复位：视图离开栈顶时清除残留的 hover 视觉。"""

from __future__ import annotations

import flet as ft

_ATTR = "_hover_reset"


class _LeaveEvent:
    """模拟 hover 离开事件。"""

    def __init__(self, control) -> None:
        self.control = control
        self.data = False


def register(control, reset) -> None:
    """登记某个控件的 hover 复位回调。"""
    try:
        setattr(control, _ATTR, reset)
    except Exception:
        pass


def _walk(root):
    """深度优先遍历控件子树。"""
    seen: set[int] = set()
    stack = [root]
    while stack:
        item = stack.pop()
        if not isinstance(item, ft.Control) or id(item) in seen:
            continue
        seen.add(id(item))
        yield item
        content = getattr(item, "content", None)
        if isinstance(content, ft.Control):
            stack.append(content)
        controls = getattr(item, "controls", None)
        if isinstance(controls, (list, tuple)):
            stack.extend(
                child for child in controls
                if isinstance(child, ft.Control)
            )


def reset_tree(root) -> None:
    """复位子树里的 hover 残留：登记回调 + 模拟离开事件。"""
    roots = root if isinstance(root, (list, tuple)) else [root]
    for item in roots:
        for control in _walk(item):
            reset = getattr(control, _ATTR, None)
            if callable(reset):
                try:
                    reset()
                except Exception:
                    pass
            handler = getattr(control, "on_hover", None)
            if callable(handler):
                try:
                    handler(_LeaveEvent(control))
                except Exception:
                    pass
