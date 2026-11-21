"""拼音感知搜索：原文、全拼（全部读音）与首字母。"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

import pykakasi
from pykakasi.kanji import Itaiji, Kanwa
from pypinyin import Style, pinyin

from bangumi.core.text_variants import fold_variants, variant_forms

_KAKASI = pykakasi.kakasi()
_KATAKANA_WORD_RE = re.compile(r"[\u30a0-\u30ffー・]+")
_KANA_RE = re.compile(r"[\u3040-\u30ff]+")
_VARIANT_KANJI = {
    "﨑": "崎",
    "髙": "高",
    "濵": "浜",
    "德": "徳",
    "塚": "塚",
    "神": "神",
    "福": "福",
    "館": "館",
    "都": "都",
}

_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _normalize_romaji(value: object) -> str:
    text = "".join(
        ch
        for ch in str(value or "").casefold()
        if ch.isascii() and ch.isalnum()
    )
    text = re.sub(r"([aeiou])\1+", r"\1", text)
    text = text.replace("ou", "o")
    text = re.sub(
        r"([bcdfghjklmnpqrstvwxyz])\1+",
        r"\1",
        text,
    )
    return text


_VOICE_PAIRS = (
    ("sh", "j"),
    ("ch", "j"),
    ("ts", "z"),
    ("s", "z"),
    ("k", "g"),
    ("t", "d"),
    ("h", "b"),
    ("h", "p"),
)


def _voice_variants(value: str) -> tuple[str, ...]:
    variants = {value}
    for source, target in _VOICE_PAIRS:
        if source in value:
            variants.add(value.replace(source, target))
        if target in value:
            variants.add(value.replace(target, source))
    return tuple(variants)


def _kana_unify(value: str) -> str:
    return "".join(
        chr(ord(ch) + 0x60)
        if 0x3041 <= ord(ch) <= 0x3096
        else ch
        for ch in value
    )


@lru_cache(maxsize=8192)
def _kanji_readings(char: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", char)
    candidates: list[str] = []
    for candidate in (
        normalized,
        fold_variants(normalized),
        *variant_forms(normalized),
    ):
        mapped = _VARIANT_KANJI.get(candidate, candidate)
        if mapped and mapped not in candidates:
            candidates.append(mapped)

    for candidate in candidates:
        table = Kanwa().load(candidate)
        entries = (table.get(candidate) or []) if table else []
        if not entries:
            continue
        values: list[str] = []
        for yomi, _condition in entries:
            romaji = _normalize_romaji(
                "".join(
                    item.get("hepburn", "")
                    for item in _KAKASI.convert(str(yomi))
                )
            )
            if not romaji:
                continue
            for value in _voice_variants(romaji):
                if value and value not in values:
                    values.append(value)
        if values:
            return tuple(values)

    for candidate in candidates:
        converted = Itaiji().convert(candidate)
        if converted and converted != candidate:
            readings = _kanji_readings(converted)
            if readings:
                return readings
    return ()


@lru_cache(maxsize=8192)
def _romaji_units(text: str) -> tuple[tuple[int, tuple[str, ...]], ...]:
    units: list[tuple[int, tuple[str, ...]]] = []
    for index, char in enumerate(text):
        if char.isascii() and char.isalnum():
            units.append((index, (char.lower(),)))
            continue
        if _KANA_RE.match(char):
            romaji = _normalize_romaji(
                "".join(
                    item.get("hepburn", "")
                    for item in _KAKASI.convert(char)
                )
            )
            if romaji:
                units.append((index, (romaji,)))
            continue
        readings = _kanji_readings(char)
        if readings:
            units.append((index, readings))
    return tuple(units)


@lru_cache(maxsize=8192)
def _units(text: str) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """(原文字符下标, 该字符的可选读音/字母) 列表；标点空格跳过。"""
    units: list[tuple[int, tuple[str, ...]]] = []
    for index, char in enumerate(text):
        if char.isspace():
            continue
        if _HAN_RE.match(char):
            groups = pinyin(char, style=Style.NORMAL, heteronym=True)
            values = tuple(
                dict.fromkeys(
                    str(part).strip().lower()
                    for group in groups
                    for part in group
                    if str(part).strip()
                )
            )
            if values:
                units.append((index, values))
            continue
        if char.isalnum():
            units.append((index, (char.lower(),)))
    return tuple(units)


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    spans = sorted(set(spans))
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _scan(units, query: str, *, initials: bool) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    total = len(units)
    first = query[0]
    for start in range(total):
        head = units[start][1]
        if isinstance(head, str):
            head = (head,)
        heads = (
            tuple(value[:1] for value in head)
            if initials
            else head
        )
        if not any(value.startswith(first) for value in heads):
            continue
        frontier = {""}
        for offset in range(start, total):
            index, alternatives = units[offset]
            if isinstance(alternatives, str):
                alternatives = (alternatives,)
            options = (
                tuple(value[:1] for value in alternatives)
                if initials
                else alternatives
            )
            nxt: set[str] = set()
            matched = False
            for prefix in frontier:
                for option in options:
                    if not option:
                        continue
                    candidate = prefix + option
                    if candidate.startswith(query):
                        matched = True
                    elif query.startswith(candidate):
                        nxt.add(candidate)
            if matched:
                spans.append((units[start][0], index + 1))
                break
            if not nxt:
                break
            frontier = nxt
    return spans


@lru_cache(maxsize=8192)
def _char_candidates(char: str) -> tuple[str, ...]:
    if char.isascii() and char.isalnum():
        return (char.lower(),)
    if _KANA_RE.match(char):
        romaji = _normalize_romaji(
            "".join(
                item.get("hepburn", "")
                for item in _KAKASI.convert(char)
            )
        )
        return (romaji,) if romaji else ()
    readings = _kanji_readings(char)
    return readings


def _sequential_spans(
    text: str,
    key: str,
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if not text or not key:
        return spans
    total_text = len(text)
    total_key = len(key)
    for start in range(total_text):
        stack = [(start, 0)]
        seen: set[tuple[int, int]] = set()
        while stack:
            ti, ki = stack.pop()
            if (ti, ki) in seen:
                continue
            seen.add((ti, ki))
            if ki >= total_key:
                if ti > start:
                    spans.append((start, ti))
                continue
            if ti >= total_text:
                continue
            char = text[ti]
            key_char = key[ki]
            if _kana_unify(fold_variants(key_char)) == _kana_unify(fold_variants(char)):
                stack.append((ti + 1, ki + 1))
            run_end = ki
            while run_end < total_key and (
                (
                    key[run_end].isascii()
                    and key[run_end].isalnum()
                )
                or _KANA_RE.match(key[run_end])
            ):
                run_end += 1
            if run_end > ki:
                run_key = _normalize_romaji(
                    "".join(
                        item.get("hepburn", "")
                        for item in _KAKASI.convert(
                            key[ki:run_end]
                        )
                    )
                )
                if run_key:
                    run_variants = _voice_variants(run_key)
                    for candidate in _char_candidates(char):
                        candidate_variants = _voice_variants(
                            candidate
                        )
                        if any(
                            value.startswith(run_key)
                            for value in candidate_variants
                        ):
                            if ti + 1 > start:
                                spans.append((start, ti + 1))
                            break
                        if any(
                            value.startswith(candidate)
                            for value in run_variants
                        ):
                            stack.append(
                                (ti + 1, ki + len(candidate))
                            )
    return spans


@lru_cache(maxsize=4096)
def _searchable(text: str, query: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    if query:
        for match in re.finditer(re.escape(query), text, re.IGNORECASE):
            spans.append((match.start(), match.end()))

    folded_text = fold_variants(text)
    folded_query = fold_variants(query)
    if folded_query:
        start = folded_text.find(folded_query)
        while start != -1:
            spans.append((start, start + len(folded_query)))
            start = folded_text.find(folded_query, start + 1)

    unified_text = _kana_unify(text)
    unified_query = _kana_unify(query)
    if unified_query:
        start = unified_text.find(unified_query)
        while start != -1:
            spans.append((start, start + len(unified_query)))
            start = unified_text.find(unified_query, start + 1)

    letters = "".join(
        char for char in query.casefold() if char.isalnum()
    )
    spans.extend(_sequential_spans(text, query))
    if not letters or not letters.isascii():
        return tuple(_merge(spans))
    units = _units(text)
    if units:
        spans.extend(_scan(units, letters, initials=False))
        spans.extend(_scan(units, letters, initials=True))
    query_key = _normalize_romaji(query)
    if query_key:
        romaji_units = _romaji_units(text)
        if romaji_units:
            spans.extend(
                _scan(romaji_units, query_key, initials=False)
            )
        for match in _KATAKANA_WORD_RE.finditer(text):
            word = match.group(0)
            romaji = _normalize_romaji(
                "".join(
                    item.get("hepburn", "")
                    for item in _KAKASI.convert(word)
                )
            )
            if len(romaji) < 2:
                continue
            before = _normalize_romaji(
                "".join(
                    item.get("hepburn", "")
                    for item in _KAKASI.convert(
                        text[: match.start()]
                    )
                )
            )
            k = 0
            if before:
                if query_key.startswith(before):
                    k = len(before)
                else:
                    for size in range(
                        1, len(query_key) + 1
                    ):
                        if before.startswith(
                            query_key[:size]
                        ):
                            k = size
                        else:
                            break
            suffix = query_key[k:]
            if len(suffix) < 2:
                continue
            best = 0.0
            for extra in (0, 1, 2):
                size = len(suffix) + extra
                if size > len(romaji):
                    continue
                ratio = SequenceMatcher(
                    None, suffix, romaji[:size]
                ).ratio()
                if ratio > best:
                    best = ratio
            if best >= 0.6:
                spans.append((match.start(), match.end()))
    return tuple(_merge(spans))


def find_spans(text: str, query: str) -> list[tuple[int, int]]:
    """返回 text 中与 query 命中的字符区间（原文/全拼/首字母）。"""
    if not query:
        return []
    return list(_searchable(str(text or ""), str(query)))


def matches(text: str, query: str) -> bool:
    return bool(find_spans(text, query))
