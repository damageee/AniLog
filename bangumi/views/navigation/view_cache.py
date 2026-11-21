"""视图控件暂存：只保留栈顶视图的控件树。

下层视图的控件从客户端卸载（换成 0 高度占位容器），返回时原样挂回。
控件对象本身留在 Python 里，因此复选框、输入框、展开状态、滚动目标
等都不需要额外序列化即可保留；客户端不需要同时渲染整条栈。
"""

from __future__ import annotations

import flet as ft

# id(view) -> (view, 原始 controls)；存 view 的强引用，避免 id 被复用。
_STASH: dict[int, tuple[object, list[ft.Control]]] = {}


def _keep_alive(view: object) -> bool:
    """页面声明 keep_alive 时不做暂存。"""
    data = getattr(view, "data", None)
    return isinstance(data, dict) and data.get("keep_alive") is True


def stash(view: object) -> None:
    """把视图控件换成一个占位容器，原控件存起来。"""
    if view is None or _keep_alive(view) or id(view) in _STASH:
        return
    controls = getattr(view, "controls", None)
    if not controls:
        return
    stashed = list(controls)
    _STASH[id(view)] = (view, stashed)
    view.controls = [ft.Container(height=0, width=0)]
    # 已从客户端卸载，再复位 hover，update() 只会抛异常被吞掉。
    from bangumi.ui.hover_state import reset_tree

    reset_tree(stashed)


def restore(view: object) -> None:
    """把暂存的控件挂回视图。"""
    entry = _STASH.pop(id(view), None)
    if entry is None:
        return
    view.controls = entry[1]
    data = getattr(view, "data", None)
    handler = (
        data.get("on_restore")
        if isinstance(data, dict)
        else None
    )
    if callable(handler):
        try:
            handler()
        except Exception:
            pass


def forget(view: object) -> None:
    """视图被移出栈时丢弃它的暂存。"""
    if view is not None:
        _STASH.pop(id(view), None)


def stash_hidden(page: ft.Page) -> None:
    """同步：栈顶视图保留控件，其余视图收起。"""
    views = getattr(page, "views", None)
    if not views:
        return
    top = views[-1]
    for view in list(views):
        if view is top:
            restore(view)
        else:
            stash(view)


