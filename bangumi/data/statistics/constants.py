"""统计常量与正则。"""

from __future__ import annotations

import re


_MINUTE_RE = re.compile(r"(\d+)\s*分钟")


_SPEC_PART_RE = re.compile(r"[+＋、,，/·|]")


_EPISODE_PART_RE = re.compile(r"(\d+)\s*(?:话|集)")


_BARE_EPISODE_RE = re.compile(r"(\d+)")


_TAG_PART_RE = re.compile(r"OVA|OAD|SP", re.IGNORECASE)


_BROADCAST_RE = re.compile(r"((?:19|20)\d{2})\s*[年./-]\s*(\d{1,2})")

SEASONS = ("冬", "春", "夏", "秋")

SEASON_CODES = ("W", "S", "U", "A")   # 冬/春/夏/秋

CATEGORY_NAMES = (
    "小说改",
    "漫画改",
    "原创",
    "游戏改",
    "电影",
    "音乐衍生",
    "跨媒体",
    "其他",
)

_COMPLETION_RE = re.compile(
    r"^\s*(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*$"
)


_MAIN_EPISODE_RE = re.compile(r"(\d+)\s*(?:话|集)")


_TAG_EPISODE_RE = re.compile(
    r"(?<![A-Z])(\d+)?\s*(?:OVA|OAD|SP)(?![A-Z])"
)


_BARE_NUMBER_RE = re.compile(r"^\s*(\d+)\s*$")

HONOR_COLUMNS = ("高产劳模", "整体发挥", "最高力作")

HONOR_TOTAL = "总览"

DATA_TAG_SEPARATORS = re.compile(r"[\r\n、,，;；|]+")
