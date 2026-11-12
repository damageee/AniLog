"""观影表格的排序键。

按字符逐个比较。字符组顺序为：数字、英文字母、汉字（按拼音）、
假名（按五十音），最后是其他字符（特殊符号）。
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from pypinyin import lazy_pinyin

from bangumi.data.dates import earliest_broadcast_date
from bangumi.data.watched_data import Record, record_anime

_GOJUON = (
    "あいうえお"
    "かきくけこ"
    "さしすせそ"
    "たちつてと"
    "なにぬねの"
    "はひふへほ"
    "まみむめも"
    "やゆよ"
    "らりるれろ"
    "わゐゑをん"
)
_GOJUON_ORDER = {char: index for index, char in enumerate(_GOJUON)}

_SMALL_KANA = {
    "ぁ": "あ",
    "ぃ": "い",
    "ぅ": "う",
    "ぇ": "え",
    "ぉ": "お",
    "っ": "つ",
    "ゃ": "や",
    "ゅ": "ゆ",
    "ょ": "よ",
    "ゎ": "わ",
    "ゕ": "か",
    "ゖ": "け",
}

_SPEC_MINUTES = re.compile(r"^(\d+(?:\.\d+)?)\s*分钟$")
_SPEC_EPISODES = re.compile(r"^(\d+)\s*话$")
_SPEC_BARE_NUMBER = re.compile(r"^\d+$")
_SPEC_LEADING_NUMBER = re.compile(r"^(\d*)\s*(.*)$", re.DOTALL)
_SPECIAL_ORDER = {"SP": 0, "OVA": 1, "OAD": 2}
_UNKNOWN_SPECIAL_ORDER = 3
_COMPLETION_DATE = re.compile(
    r"^\s*(\d{4})\.(\d{1,2})\.(\d{1,2})\s*$"
)


def record_broadcast_sort_key(
    record: Record,
    index: int,
) -> tuple[int, int, int, int, int]:
    """有日期的记录排在前，其余保持原表格顺序。"""
    date = earliest_broadcast_date(
        str(record.get("broadcast", "") or "")
    )
    if date is None:
        return (1, 0, 0, 0, index)
    year, month, day = date
    return (0, year, month, day, index)


def sort_records_by_broadcast(records: list[Record]) -> list[Record]:
    """按首次放送日期排序，以表格顺序作为并列时的次序。"""
    return [
        record
        for _, record in sorted(
            enumerate(records),
            key=lambda item: record_broadcast_sort_key(
                item[1],
                item[0],
            ),
        )
    ]


def sort_detail_items(items: list[tuple[str, Record]]) -> list[tuple[str, Record]]:
    """按首次放送日期排序带标签的记录；无日期的排在最后。"""
    if not items:
        return []
    earliest: dict[str, tuple[int, int, int]] = {}
    for text, record in items:
        date = earliest_broadcast_date(
            str(record.get("broadcast") or "")
        )
        if date is None:
            continue
        current = earliest.get(text)
        if current is None or date < current:
            earliest[text] = date

    def key(entry: tuple[int, tuple[str, Record]]):
        index, (text, record) = entry
        date = earliest.get(text)
        if date is None:
            name = record_anime(record) or text
            return (1, 0, 0, 0, sort_key(name), index)
        year, month, day = date
        return (0, year, month, day, "", index)

    return [item for _, item in sorted(enumerate(items), key=key)]


def sort_key(value: str) -> tuple:
    folded = value.casefold()
    character_keys = tuple(_character_key(char) for char in folded)
    # 仅当字符键完全相同时，才比较这些值以打破并列。
    return (character_keys, folded)


@lru_cache(maxsize=4096)
def completion_sort_key(value: str) -> tuple:
    """对 ``YYYY.MM.DD`` 补完日期排序，其他值排在最后。"""
    match = _COMPLETION_DATE.match(str(value or ""))
    if match is None:
        return (1, 0, 0, 0, sort_key(str(value or "")))
    year, month, day = (int(part) for part in match.groups())
    return (0, year, month, day, sort_key(str(value or "")))


@lru_cache(maxsize=4096)
def specification_sort_key(value: str) -> tuple:
    """观影表格 ``specification`` 列的排序键。"""
    minutes = 0.0
    episodes = 0
    special_count = 0
    special_order: int | None = None
    has_minutes = False
    has_episodes = False
    has_special = False

    for part in re.split(r"[+＋]", value):
        part = part.strip()
        if not part:
            continue

        match = _SPEC_MINUTES.match(part)
        if match is not None:
            minutes += float(match.group(1))
            has_minutes = True
            continue

        match = _SPEC_EPISODES.match(part)
        if match is not None:
            episodes += int(match.group(1))
            has_episodes = True
            continue

        if _SPEC_BARE_NUMBER.match(part):
            episodes += int(part)
            has_episodes = True
            continue

        match = _SPEC_LEADING_NUMBER.match(part)
        if match is not None:
            count_text, remainder = match.groups()
            word = remainder.strip()
            if word and any(char.isalpha() for char in word):
                count = int(count_text) if count_text else 1
                order = _SPECIAL_ORDER.get(
                    word.upper(),
                    _UNKNOWN_SPECIAL_ORDER,
                )
                if special_order is None or order < special_order:
                    special_order = order
                special_count += count
                has_special = True

    if has_minutes:
        return (0, minutes, 0, sort_key(value))
    if has_episodes:
        return (2, episodes + special_count, 0, sort_key(value))
    if has_special:
        return (1, special_order or 0, special_count, sort_key(value))
    return (3, 0, 0, sort_key(value))


@lru_cache(maxsize=4096)
def _character_key(char: str) -> tuple:
    if char.isdigit():
        return (0, unicodedata.digit(char, 0))
    normalized = unicodedata.normalize("NFKC", char)
    if len(normalized) == 1 and normalized.isascii() and normalized.isalpha():
        return (1, normalized)
    if _is_chinese(char):
        return (2, _pinyin(char))
    if _is_kana(char):
        kana_key = _kana_key(char)
        if kana_key is not None:
            return (3, kana_key)
    return (4, char)


@lru_cache(maxsize=4096)
def _pinyin(char: str) -> str:
    syllables = lazy_pinyin(char)
    return syllables[0] if syllables else char


def _is_chinese(char: str) -> bool:
    code = ord(char)
    return (
        char == "〇"
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2FA1F
    )


def _is_kana(char: str) -> bool:
    code = ord(char)
    return (
        0x3040 <= code <= 0x30FF
        or 0x31F0 <= code <= 0x31FF
        or 0xFF66 <= code <= 0xFF9F
    )


@lru_cache(maxsize=256)
def _kana_key(char: str) -> int | None:
    # 先规范化半角片假名，再处理平假名/片假名，然后处理浊音
    # 符号和小假名，使 が/ぎ/... 与 か/き/... 排在同一行。
    normalized = unicodedata.normalize("NFKC", char)
    if len(normalized) != 1:
        return None
    code = ord(normalized)
    if 0x30A1 <= code <= 0x30F6:
        normalized = chr(code - 0x60)
    decomposed = unicodedata.normalize("NFD", normalized)
    base = _SMALL_KANA.get(decomposed[0], decomposed[0])
    index = _GOJUON_ORDER.get(base)
    if index is None:
        return None
    # 将浊音假名排在其清音形式之后、下一个音节之前：
    # か < が < き.
    voicing = 0
    if "\u3099" in decomposed:
        voicing = 1
    elif "\u309a" in decomposed:
        voicing = 2
    return index * 3 + voicing
