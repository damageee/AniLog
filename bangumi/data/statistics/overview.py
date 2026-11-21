"""总览统计。"""

from __future__ import annotations

import re

from bangumi.data.watched_data import Record, load_records
from .constants import CATEGORY_NAMES, _MINUTE_RE
from .models import OverviewData
from .records import (
    _anime_items,
    _detail_item,
    _entry_items,
    _name,
    _record_item,
    _specification,
    _sum_spec,
)


def _parse_specification(
    specification: str,
) -> dict[str, tuple[int, int]]:
    """按 +/＋ 拆段，返回 {类型: (部数, 集数)}。"""
    parts = [
        part.strip()
        for part in re.split(r"[+＋]", specification)
        if part.strip()
    ]
    if not parts:
        parts = [""]
    result: dict[str, tuple[int, int]] = {}
    for part in parts:
        upper = part.upper()
        if "OVA" in upper:
            kind = "ova"
        elif "OAD" in upper:
            kind = "oad"
        elif "SP" in upper:
            kind = "sp"
        elif "电影" in part or "剧场版" in part:
            kind = "movie"
        elif "分钟" in part:
            kind = "movie"
        else:
            kind = "tv"
        numbers = re.findall(r"\d+", part)
        count = int(numbers[0]) if numbers else 0
        previous = result.get(kind)
        if previous is None:
            result[kind] = (1, count)
        else:
            result[kind] = (previous[0], previous[1] + count)
    return result


def overview_data(records: list[Record] | None = None) -> OverviewData:
    """根据观影记录计算总览数字与详情名称。

    各类别互斥：只要规格含有集数部分（纯数字、``N话`` 或 ``N集``），
    即使同时带有 OVA/OAD/SP 也算 TV。否则优先级为
    ``OVA > OAD > SP > 电影/剧场版``。
    """
    if records is None:
        records = load_records()

    tv_records: list[Record] = []
    ova_records: list[Record] = []
    oad_records: list[Record] = []
    sp_records: list[Record] = []
    feature_records: list[Record] = []
    theater_records: list[Record] = []
    tv_episodes = 0
    ova_episodes = 0
    oad_episodes = 0
    sp_episodes = 0

    for record in records:
        specification = _specification(record)
        parsed = _parse_specification(specification)
        if "tv" in parsed:
            tv_records.append(record)
            tv_episodes += parsed["tv"][1]
        if "ova" in parsed:
            ova_records.append(record)
            ova_episodes += parsed["ova"][1]
        if "oad" in parsed:
            oad_records.append(record)
            oad_episodes += parsed["oad"][1]
        if "sp" in parsed:
            sp_records.append(record)
            sp_episodes += parsed["sp"][1]
        if "movie" in parsed:
            if "剧场版" in _name(record):
                theater_records.append(record)
            else:
                feature_records.append(record)

    movie_records = feature_records + theater_records
    sequel_records = [
        record for record in records if record.get("sequel") is True
    ]

    entry_items = _entry_items(records)
    sequel_items = _entry_items(sequel_records)

    category_totals = {name: 0 for name in CATEGORY_NAMES}
    for record in records:
        name = str(record.get("category") or "").strip()
        if name not in category_totals:
            name = "其他"
        category_totals[name] += 1
    category_counts = [
        (name, count)
        for name, count in category_totals.items()
        if count
    ]

    anime_items = _anime_items(records)

    return OverviewData(
        total=len(records),
        entries=len(entry_items),
        anime_count=len(anime_items),
        tv_count=len(tv_records),
        tv_episodes=tv_episodes,
        ova_count=len(ova_records),
        ova_episodes=ova_episodes,
        oad_count=len(oad_records),
        oad_episodes=oad_episodes,
        sp_count=len(sp_records),
        sp_episodes=sp_episodes,
        movie_count=len(movie_records),
        movie_minutes=_sum_spec(movie_records, _MINUTE_RE),
        feature_count=len(feature_records),
        theater_count=len(theater_records),
        sequel_count=len(sequel_items),
        category_counts=category_counts,
        records=records,
        total_items=[_record_item(record) for record in records],
        entry_items=entry_items,
        anime_items=anime_items,
        tv_items=[_detail_item(record) for record in tv_records],
        ova_items=[_detail_item(record) for record in ova_records],
        oad_items=[_detail_item(record) for record in oad_records],
        sp_items=[_detail_item(record) for record in sp_records],
        movie_items=[_detail_item(record) for record in movie_records],
        sequel_items=sequel_items,
    )
