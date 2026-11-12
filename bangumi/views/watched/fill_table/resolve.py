"""解析 Bangumi 条目。"""

from __future__ import annotations

from bangumi.services.bgm_search import NAME_IDS, _expand_abbreviation, search_bgm


def resolve_subject(anime: str, power: str) -> dict:
    matched = None
    if anime in NAME_IDS:
        matched = anime
    else:
        expanded = _expand_abbreviation(anime)
        if expanded in NAME_IDS:
            matched = expanded
    if matched is not None:
        return {
            "bgm_id": NAME_IDS[matched],
            "name_cn": matched,
            "score": 1.0,
            "manual": False,
            "results": [],
        }
    results = search_bgm(anime)
    if not results:
        return {
            "bgm_id": None,
            "name_cn": "",
            "score": 0.0,
            "manual": False,
            "results": [],
        }
    first = results[0]
    score = float(first.get("score") or 0.0)
    manual = False
    if power == "precise":
        manual = first.get("confidence") != "exact"
    elif power == "confident":
        manual = first.get("confidence") == "fallback"
    elif power == "fairly":
        manual = score < 0.70
    elif power == "loose":
        manual = score < 0.50
    name = str(first.get("name_cn") or first.get("name") or "").strip()
    return {
        "bgm_id": int(first.get("id")),
        "name_cn": name,
        "score": score,
        "manual": manual,
        "results": results,
    }
