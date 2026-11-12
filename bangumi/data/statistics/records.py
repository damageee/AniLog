"""记录行的名称与规格辅助。"""

from __future__ import annotations

import re

from bangumi.data.watched_data import (
    Record,
    entry_group_key,
    record_anime,
    record_title,
)
from .constants import (
    _BARE_EPISODE_RE,
    _EPISODE_PART_RE,
    _SPEC_PART_RE,
    _TAG_PART_RE,
)
from .models import DetailItem


def _name(record: Record) -> str:
    return record_title(record)


def _specification(record: Record) -> str:
    return str(record.get("specification") or "").strip()


def _spec_episodes(specification: str) -> tuple[bool, int]:
    """返回规格字符串的 ``(has_episode_part, episode_total)``。

    只有纯数字和 ``N话``/``N集`` 部分计入集数；因此 ``12话 + 2OVA``
    有 12 集，而 ``2OVA`` 没有集数。``OVA``/``OAD``/``SP`` 和分钟部分
    从不增加集数。
    """
    text = str(specification or "").strip()
    if not text:
        return False, 0
    has_episode = False
    total = 0
    for raw_part in _SPEC_PART_RE.split(text):
        part = raw_part.strip()
        if not part:
            continue
        if _TAG_PART_RE.search(part) or "分钟" in part:
            continue
        matched = list(_EPISODE_PART_RE.finditer(part))
        if matched:
            has_episode = True
            total += sum(int(match.group(1)) for match in matched)
            continue
        bare = _BARE_EPISODE_RE.fullmatch(part)
        if bare is not None:
            has_episode = True
            total += int(bare.group(1))
    return has_episode, total


def _sum_spec(records: list[Record], pattern: re.Pattern[str]) -> int:
    total = 0
    for record in records:
        match = pattern.search(_specification(record))
        if match is not None:
            total += int(match.group(1))
    return total


def _record_item(record: Record) -> DetailItem:
    return (
        _name(record) or entry_group_key(record),
        record,
    )


def _entry_items(records: list[Record]) -> list[DetailItem]:
    items: list[DetailItem] = []
    seen: set[str] = set()
    for record in records:
        key = entry_group_key(record)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append((key, record))
    return items


def _anime_items(records: list[Record]) -> list[DetailItem]:
    items: list[DetailItem] = []
    for record in records:
        anime = record_anime(record)
        if not anime:
            continue
        items.append((anime, record))
    return items


def _row_text(record: Record) -> str:
    return " · ".join(
        part
        for part in (_name(record), _specification(record))
        if part
    )


def _detail_item(record: Record) -> DetailItem:
    return (_row_text(record), record)
