"""已追清单的持久化。"""

from __future__ import annotations

from bangumi.core.storage import read_json, watchlist_file, write_json


def _clean(values: object) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe(
    high: object,
    low: object,
) -> tuple[list[str], list[str]]:
    clean_high = _clean(high)
    seen = set(clean_high)
    clean_low = [
        name for name in _clean(low) if name not in seen
    ]
    return clean_high, clean_low


def load_watchlist() -> tuple[list[str], list[str]]:
    """返回 ``(high, low)``；文件缺失或损坏时返回空列表。"""
    path = watchlist_file()
    if not path.is_file():
        return [], []
    try:
        data = read_json(path)
    except Exception:
        return [], []
    if not isinstance(data, dict):
        return [], []
    return _dedupe(data.get("high"), data.get("low"))


def save_watchlist(high: list[str], low: list[str]) -> None:
    clean_high, clean_low = _dedupe(high, low)
    write_json(
        watchlist_file(),
        {"high": clean_high, "low": clean_low},
    )
