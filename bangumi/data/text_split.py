"""通用文本切分。"""

from __future__ import annotations



def split_unique(value, separators) -> list[str]:
    if isinstance(value, (list, tuple)):
        parts = [str(part) for part in value]
    elif hasattr(separators, "split"):
        parts = separators.split(str(value or ""))
    else:
        parts = str(value or "").split(str(separators))
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        item = part.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
