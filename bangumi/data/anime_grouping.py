"""动画标题去重、按前缀分组（纯数据模块）。"""

from __future__ import annotations

from bangumi.data.watched_data import load_records

_SPACE = " "
_STRIP_WORDS = (
    "剧场版",
    "电影",
    "TV",
    "OVA",
    "OAD",
    "SP",
    "特别篇",
    "特典",
)
# 只在结尾裁剪的成对符号。
_PAIRED = set(
    " 、'~～[]【】「」“”‘’()（）《》〈〉"
)


def _is_latin(char: str) -> bool:
    return ("a" <= char <= "z") or ("A" <= char <= "Z")


def _is_digit(char: str) -> bool:
    return "0" <= char <= "9"


def _is_han(char: str) -> bool:
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
    )


def _is_kana(char: str) -> bool:
    code = ord(char)
    return 0x3040 <= code <= 0x30FF


def _is_cjk(char: str) -> bool:
    return _is_han(char) or _is_kana(char)


def _is_alnum(char: str) -> bool:
    return _is_latin(char) or _is_digit(char)


def _is_special(char: str) -> bool:
    """既非拉丁字母/数字，也非中日文字符。"""
    return not (_is_alnum(char) or _is_cjk(char))


def _strip_prefix_words(text: str) -> str:
    """反复去掉开头的剧场版/电影/TV/OVA 等词及其后的空格。"""
    value = text.strip()
    changed = True
    while changed:
        changed = False
        for word in _STRIP_WORDS:
            if value.startswith(word):
                value = value[len(word):].lstrip()
                changed = True
                break
    return value


def _scan_prefix(text: str) -> str:
    """计算用于匹配的前缀。"""
    if not text:
        return ""
    first = text[0]
    if _is_alnum(first) or _is_special(first):
        index = text.find(_SPACE)
        return text if index < 0 else text[:index]

    chars: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == _SPACE or _is_special(char):
            break
        if _is_alnum(char):
            end = index
            while end < length and _is_alnum(text[end]):
                end += 1
            following = text[end] if end < length else ""
            if end >= length or following == _SPACE or _is_special(
                following
            ):
                break
            chars.append(text[index:end])
            index = end
            continue
        chars.append(char)
        index += 1

    prefix = "".join(chars)
    if prefix:
        return prefix
    # 兜底：取到第一个空格。
    index = text.find(_SPACE)
    return text if index < 0 else text[:index]


def _common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    prefix = strings[0]
    for value in strings[1:]:
        while not value.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def _trim_paired(text: str) -> str:
    """裁掉结尾的空格与成对符号。"""
    end = len(text)
    while end > 0 and text[end - 1] in _PAIRED:
        end -= 1
    return text[:end]


def group_anime_titles(titles: list[str]) -> dict[str, list[str]]:
    """标题去重后按前缀分组，返回 {prefix: [原始标题]}。"""
    ordered: list[str] = []
    seen: set[str] = set()
    for title in titles:
        if title not in seen:
            seen.add(title)
            ordered.append(title)

    watched = {
        str(record.get("anime") or "").strip()
        for record in load_records()
    }
    cleaned = [
        title for title in ordered if title.strip() not in watched
    ]

    primes = [_strip_prefix_words(title) for title in cleaned]
    remaining = list(range(len(cleaned)))
    result: dict[str, list[str]] = {}

    while remaining:
        seed = remaining[0]
        prefix_ = _scan_prefix(primes[seed])
        matches = [
            index
            for index in remaining
            if primes[index].startswith(prefix_)
        ]
        if len(matches) == 1:
            prefix = primes[matches[0]]
        else:
            prefix = _common_prefix(
                [primes[index] for index in matches]
            )
            prefix = _trim_paired(prefix)
            if len(prefix) < len(prefix_):
                prefix = prefix_
        result.setdefault(prefix, []).extend(
            cleaned[index] for index in matches
        )
        removed = set(matches)
        remaining = [
            index for index in remaining if index not in removed
        ]

    return result
