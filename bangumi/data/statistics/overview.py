"""总览统计。"""

from __future__ import annotations

from bangumi.data.watched_data import Record, load_records
from .constants import CATEGORY_NAMES, _MINUTE_RE
from .models import OverviewData
from .records import (
    _anime_items,
    _detail_item,
    _entry_items,
    _name,
    _record_item,
    _spec_episodes,
    _specification,
    _sum_spec,
)


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

    for record in records:
        specification = _specification(record)
        has_episode, episodes = _spec_episodes(specification)
        upper = specification.upper()
        if not specification:
            tv_records.append(record)
        elif has_episode and episodes > 1:
            tv_records.append(record)
            tv_episodes += episodes
        elif "OVA" in upper:
            ova_records.append(record)
        elif "OAD" in upper:
            oad_records.append(record)
        elif "SP" in upper:
            sp_records.append(record)
        elif "分钟" in specification:
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
        oad_count=len(oad_records),
        sp_count=len(sp_records),
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
