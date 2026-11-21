"""已追名称归一化与重复判断。"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from bangumi.views.watched.constants import (
    WATCHLIST_FUZZY_MIN,
    WATCHLIST_FUZZY_RATIO,
    WATCHLIST_LENGTH_RATIO,
)
from bangumi.data.watched_data import Record
from bangumi.core.text_variants import fold_variants


def normalize_watchlist_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = fold_variants(text).casefold()
    return "".join(char for char in text if char.isalnum())
WATCHLIST_FINAL_RE = re.compile(r"(?:最终季|最终章)$")
WATCHLIST_SEASON_RE = re.compile(
    r"(?:"
    r"第?([0-9]+|[一二三四五六七八九十]+)(?:季度|季|期|部|章)"
    r"|season([0-9]+)"
    r"|([0-9]+)(?:st|nd|rd|th)season"
    r"|part([0-9]+)"
    r"|(i{1,3}|iv|vi{1,3}|ix|x|xi{0,2}|v)"
    r")$"
)
WATCHLIST_DECOR_RE = re.compile(
    r"(?:剧场版|劇場版|电影|特别篇|ova|oad|sp)"
    r"|(?:第?[0-9]+话|第?[一二三四五六七八九十]+话|第?[0-9]+集|第?[一二三四五六七八九十]+集)"
)
CN_NUM = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
def season_number(raw: str) -> int | None:
    text = str(raw or "").strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text in CN_NUM:
        return CN_NUM[text]
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CN_NUM.get(left, 1) if left else 1
        ones = CN_NUM.get(right, 0) if right else 0
        return tens * 10 + ones
    roman = {"i": 1, "v": 5, "x": 10}
    total = 0
    previous = 0
    for char in reversed(text):
        if char not in roman:
            return None
        value = roman[char]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total or None
def watchlist_base(value: str) -> tuple[str, str]:
    """返回 (base_name, season_key)。"""
    text = str(value or "")
    final = False
    while True:
        match = WATCHLIST_FINAL_RE.search(text)
        if match is None:
            break
        final = True
        text = text[: match.start()]
    season = ""
    match = WATCHLIST_SEASON_RE.search(text)
    if match is not None:
        raw = next((group for group in match.groups() if group), "")
        number = season_number(raw)
        if number is not None:
            season = str(number)
            text = text[: match.start()]
    if final and not season:
        season = "final"
    text = WATCHLIST_DECOR_RE.sub("", text)
    if not text:
        return str(value or ""), season or "1"
    return text, season or "1"
def watchlist_names_match(left: str, right: str) -> bool:
    first = normalize_watchlist_name(left)
    second = normalize_watchlist_name(right)
    if not first or not second:
        return False
    if first == second:
        return True
    base_first, season_first = watchlist_base(first)
    base_second, season_second = watchlist_base(second)
    if base_first and base_second and base_first == base_second:
        return season_first == season_second
    shorter, longer = (
        (base_first, base_second)
        if len(base_first) <= len(base_second)
        else (base_second, base_first)
    )
    if (
        len(shorter) < WATCHLIST_FUZZY_MIN
        or len(longer) < WATCHLIST_FUZZY_MIN
    ):
        return False
    if len(shorter) / len(longer) < WATCHLIST_LENGTH_RATIO:
        return False
    return (
        SequenceMatcher(None, base_first, base_second).ratio()
        >= WATCHLIST_FUZZY_RATIO
    )
def duplicate_watchlist_names(
    record: Record,
    names: list[str],
) -> list[str]:
    fields = [
        str(record.get("anime") or ""),
        str(record.get("entry") or ""),
    ]
    fields = [field for field in fields if field.strip()]
    matched: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not name or name in seen:
            continue
        if any(
            watchlist_names_match(field, name) for field in fields
        ):
            seen.add(name)
            matched.append(name)
    return matched
