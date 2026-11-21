"""随机页面的页面级会话缓存（按 View 实例保存）。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.view_state import state_for
from bangumi.views.random.state import RandomParams

# 视图尚未创建时的临时会话，创建完成后绑定到 view。
_PENDING: dict[int, tuple[ft.Page, dict]] = {}


def _new_session() -> dict:
    return {
        "items": [],  # [{"b64": str, "ratio": float, "json": dict}]
        "params": RandomParams(),
        "token": 0,
        "refresh": False,
        "seen_ids": set(),
        "skip_auto": False,
    }


def _random_view(page: ft.Page):
    for view in reversed(page.views):
        if str(getattr(view, "route", "") or "") == "/random":
            return view
    return None


def session(page: ft.Page) -> dict:
    """按随机页 View 缓存图片、JSON、参数与循环 token。"""
    view = _random_view(page)
    if view is not None:
        data = state_for(view).get("random")
        if not isinstance(data, dict):
            data = _new_session()
            state_for(view)["random"] = data
        _PENDING.pop(id(page), None)
        return data
    pending = _PENDING.get(id(page))
    if pending is not None and pending[0] is page:
        return pending[1]
    data = _new_session()
    _PENDING[id(page)] = (page, data)
    return data


def bind(view: ft.View, page: ft.Page, data: dict | None = None) -> dict:
    """把构造期会话绑定到新建的随机页 View。"""
    if not isinstance(data, dict):
        pending = _PENDING.pop(id(page), None)
        data = (
            pending[1]
            if pending is not None and pending[0] is page
            else _new_session()
        )
    else:
        _PENDING.pop(id(page), None)
    state_for(view)["random"] = data
    return data
