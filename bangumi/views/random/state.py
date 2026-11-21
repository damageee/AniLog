"""随机页面参数状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import flet as ft

DEFAULT_TYPES = ["tv", "movie", "ova", "special", "tv_special"]


@dataclass
class RandomParams:
    q: str = ""
    type: list[str] = field(
        default_factory=lambda: list(DEFAULT_TYPES)
    )
    status: list[str] = field(default_factory=list)
    rating: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=list)
    voice_language: list[str] = field(
        default_factory=lambda: ["japanese"]
    )
    min_score: float = 0.0
    max_score: float = 10.0
    min_members: int = 0
    max_members: int = 2000000000
    min_year: int = 1930
    max_year: int = date.today().year
    season: list[str] = field(default_factory=list)
    # 设置页确认后需要重新随机；返回时不再自动开设置。
    params_dirty: bool = False
    suppress_auto_settings: bool = False
    preset: str = "无"


PRESETS: dict[str, dict] = {
    "无": {},
    "热门": {"min_members": 1000000},
    "知名": {"min_members": 500000},
    "常见": {"min_members": 300000},
    "佳作": {"min_members": 200000, "min_score": 8.50},
    "优秀": {
        "min_members": 80000,
        "min_score": 7.50,
        "max_score": 8.49,
    },
    "一般": {
        "min_members": 50000,
        "min_score": 7.00,
        "max_score": 7.49,
    },
    "小众": {"max_members": 500000, "min_score": 7.30},
    "00前": {"max_year": 1999},
    "00年代": {
        "min_year": 2000,
        "max_year": 2009,
        "min_members": 50000,
    },
    "10年代": {
        "min_year": 2010,
        "max_year": 2019,
        "min_members": 100000,
    },
    "20年代": {
        "min_year": 2020,
        "max_year": date.today().year,
        "min_members": 30000,
    },
}


def get_state(page: ft.Page) -> RandomParams:
    """读取当前随机页 View 的参数。"""
    from bangumi.views.random.session import session

    data = session(page)
    params = data.get("params")
    if not isinstance(params, RandomParams):
        params = RandomParams()
        data["params"] = params
    return params


def to_query(params: RandomParams) -> dict[str, str]:
    """把参数转换为请求查询串。"""
    query: dict[str, str] = {}
    if params.q:
        query["q"] = params.q
    for key in (
        "type",
        "status",
        "rating",
        "source",
        "voice_language",
        "season",
    ):
        values = getattr(params, key)
        if values:
            query[key] = ",".join(values)
    query["min_score"] = str(params.min_score)
    query["max_score"] = str(params.max_score)
    if params.min_members:
        query["min_members"] = str(params.min_members)
    if params.max_members != 2000000000:
        query["max_members"] = str(params.max_members)
    query["min_year"] = str(params.min_year)
    query["max_year"] = str(params.max_year)
    return query


def skip_auto_settings(page: ft.Page) -> bool:
    from bangumi.views.random.session import session

    return bool(session(page).get("skip_auto"))


def set_skip_auto_settings(
    page: ft.Page,
    value: bool = True,
) -> None:
    from bangumi.views.random.session import session

    session(page)["skip_auto"] = value


def reset_state(page: ft.Page) -> RandomParams:
    """重置随机参数为全新的默认值。"""
    from bangumi.views.random.session import session

    fresh = RandomParams()
    data = session(page)
    data["params"] = fresh
    data["skip_auto"] = False
    return fresh
