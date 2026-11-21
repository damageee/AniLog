"""角色代表性打分算法的预处理缓存。

本模块只依赖观影记录，不依赖任何视图：

- 按 ``entry`` 聚合系列，计算系列评分、系列百分位与系列权重；
- 解析 ``role`` 单元格，按 ``(声优, entry, 角色全名)`` 聚合出场；
- 计算每个角色的代表性分数与置信度。

应用启动或 ``watched.json`` 变化后调用 :func:`refresh` 重建索引。
"""

from __future__ import annotations

import bisect
import math
import re
import statistics
import threading
import time
from itertools import combinations
from dataclasses import dataclass

from bangumi.data.watched_data import Record, entry_group_key

_ROLE_RE = re.compile(r"^(.*?)[\(（]([^()（）]*)[\)）]\s*$")
_YEAR_RE = re.compile(r"(\d{4})")

_GENERIC_WORDS = (
    "生徒", "学生", "店員", "通行人", "観客", "記者", "看護", "母親",
    "父親", "兵士", "村人", "市民", "客", "係員", "受付", "運転手",
    "医師", "警官", "同級生", "少年", "少女", "部下", "秘書", "執事",
    "メイド", "部員", "店長", "駅員", "司会", "騎士", "研究員", "助手",
    "祖母", "祖父", "妹", "弟", "兄", "姉", "子供", "ファン",
    "観光客", "担任", "先生", "隊員",
    "の父", "の母", "の息子", "の娘", "の兄", "の弟",
    "の姉", "の妹", "の祖父", "の祖母", "の叔父", "の叔母",
)
_GENERIC_RE = re.compile("|".join(_GENERIC_WORDS))

# 角色重要度权重
_POS_WEIGHT = 0.55
_REC_WEIGHT = 0.20
_CORE_WEIGHT = 0.15
_STAB_WEIGHT = 0.10
_CORE_REC = 0.6
_CONF_REC = 0.6
_CORE_POS = 0.35
_GENERIC_PENALTY = 0.25
_GENERIC_PENALTY_MOST = 0.5

# 位置分：相对百分位 + 核心深度带 + 层级先验
_CORE_BAND_BASE = 4.0
_CORE_BAND_SLOPE = 0.1
_POS_PCT_WEIGHT = 0.30
_POS_DEPTH_WEIGHT = 0.50
_POS_TIER_WEIGHT = 0.20

# 系列权重
_EPISODE_BASE = 12.0
_EPISODE_ALPHA = 0.11
_EPISODE_CAP = 1.50
_MINUTES_PER_EPISODE = 21.0

# 角色总分直接使用 prominence * W[e]


@dataclass(frozen=True, slots=True)
class EntryStats:
    """一个系列（``entry``）的评分与权重。"""

    name: str
    size: int
    score: float
    percentile: float
    weight: float
    episode_factor: float
    imputed: bool


@dataclass(frozen=True, slots=True)
class RoleScore:
    """一个声优在某个角色上的代表性分数。"""

    cv: str
    entry: str
    character: str
    score: float
    confidence: float
    appearances: int
    entry_size: int
    position: float
    recurrence: float
    core: float
    stability: float
    series_score: float
    entry_weight: float
    best_anime: str
    best_rating: float
    best_year: int | None


@dataclass(frozen=True, slots=True)
class PreworkIndex:
    """一次预处理得到的只读索引。"""

    index_id: int
    built_at: float
    entries: dict[str, EntryStats]
    roles: dict[str, tuple[RoleScore, ...]]
    cowork: dict[str, dict[str, int]]
    cowork_names: dict[str, str]
    global_mean: float
    series_count: int


def _parse_rating(value: object) -> float | None:
    try:
        rating = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return rating if 0 <= rating <= 100 else None


def _parse_year(value: object) -> int | None:
    match = _YEAR_RE.search(str(value or ""))
    return int(match.group(1)) if match else None


def _normalize_name(value: object) -> str:
    """全名归一化：去掉空白后精确匹配，不做别名合并。"""

    return "".join(str(value or "").split()).casefold()


def _position_score(idx: int, total: int) -> float:
    if total <= 1:
        return 1.0
    core_band = _CORE_BAND_BASE + _CORE_BAND_SLOPE * total
    percentile = 1.0 - idx / (total - 1)
    if idx <= core_band:
        depth = 0.88 - 0.08 * (idx / core_band)
    else:
        x = (idx - core_band) / core_band
        depth = 0.80 / (1.0 + 1.5 * x * x)
    if idx == 0:
        tier = 1.00
    elif idx == 1:
        tier = 0.90
    elif idx == 2:
        tier = 0.70
    elif idx == 3:
        tier = 0.55
    elif idx < core_band:
        tier = 0.35
    else:
        tier = 0.0
    return (
        _POS_PCT_WEIGHT * percentile
        + _POS_DEPTH_WEIGHT * depth
        + _POS_TIER_WEIGHT * tier
    )


def _parse_role_lines(value: object) -> list[tuple[str, list[str]]]:
    """解析 ``角色名(声优)``，支持一行多个声优。"""

    result: list[tuple[str, list[str]]] = []
    for line in str(value or "").splitlines():
        text = line.strip()
        if not text:
            continue
        match = _ROLE_RE.match(text)
        if not match:
            continue
        character = match.group(1).strip()
        cvs = [
            part.strip()
            for part in re.split(r"[/／]", match.group(2))
            if part.strip()
        ]
        if character and cvs:
            result.append((character, cvs))
    return result


def _spec_episode_parts(value: object) -> tuple[float, float]:
    """返回 (话数, 分钟数)；特典无数字按 1 计。"""
    text = str(value or "").strip()
    episodes = 0.0
    minutes = 0.0
    for raw in re.split(r"[+＋、·|]", text):
        part = raw.strip()
        if not part:
            continue
        minute_matches = re.findall(r"(\d+(?:\.\d+)?)\s*分钟", part)
        for number in minute_matches:
            minutes += float(number)
        part_episodes = 0.0
        matched = False
        for number in re.findall(r"(\d+)\s*(?:话|集)", part):
            part_episodes += float(number)
            matched = True
        special = re.search(r"(OVA|OAD|SP)", part, re.IGNORECASE)
        if special is not None:
            prefix = part[: special.start()].strip()
            count = float(prefix) if prefix.isdigit() and prefix else 1.0
            part_episodes += count
            matched = True
        if not matched and not minute_matches and part.isdigit():
            part_episodes += float(part)
        episodes += part_episodes
    return episodes, minutes


def _build_works(
    records: list[Record],
) -> tuple[list[dict], dict[str, list[int]]]:
    works: list[dict] = []
    entry_works: dict[str, list[int]] = {}
    for work_id, record in enumerate(records):
        entry = entry_group_key(record)
        episodes, minutes = _spec_episode_parts(
            record.get("specification")
        )
        works.append(
            {
                "id": work_id,
                "anime": str(record.get("anime") or "").strip(),
                "entry": entry,
                "rating": _parse_rating(record.get("rating")),
                "year": _parse_year(record.get("broadcast")),
                "role_total": 0,
                "episodes": episodes,
                "minutes": minutes,
            }
        )
        entry_works.setdefault(entry, []).append(work_id)
    return works, entry_works


def _build_entries(
    works: list[dict],
    entry_works: dict[str, list[int]],
) -> tuple[dict[str, EntryStats], float, int]:
    all_ratings = [
        work["rating"] for work in works if work["rating"] is not None
    ]
    global_mean = statistics.fmean(all_ratings) if all_ratings else 100.0

    raw: dict[str, tuple[float, bool]] = {}
    for entry, work_ids in entry_works.items():
        rated = [
            works[work_id]["rating"]
            for work_id in work_ids
            if works[work_id]["rating"] is not None
        ]
        if rated:
            raw[entry] = (max(rated), False)
        else:
            raw[entry] = (global_mean, True)

    series_scores = sorted(
        score for score, imputed in raw.values() if not imputed
    )
    series_count = len(series_scores)

    entries: dict[str, EntryStats] = {}
    for entry, (score, imputed) in raw.items():
        work_ids = entry_works[entry]
        if series_scores:
            low = bisect.bisect_left(series_scores, score)
            high = bisect.bisect_right(series_scores, score)
            percentile = (
                low + 0.5 * (high - low)
            ) / series_count
        else:
            percentile = 0.5
        size = len(entry_works[entry])
        q = (score / 100.0) ** 4
        series_episodes = sum(
            works[work_id]["episodes"] for work_id in work_ids
        ) + (
            sum(
                works[work_id]["minutes"]
                for work_id in work_ids
            )
            / _MINUTES_PER_EPISODE
        )
        episode_factor = min(
            _EPISODE_CAP,
            1.0
            + _EPISODE_ALPHA
            * math.log2(
                max(_EPISODE_BASE, series_episodes) / _EPISODE_BASE
            ),
        )
        weight = q * episode_factor
        entries[entry] = EntryStats(
            name=entry,
            size=size,
            score=score,
            percentile=percentile,
            weight=weight,
            episode_factor=episode_factor,
            imputed=imputed,
        )
    return entries, global_mean, series_count


def _split_character_names(character: str) -> list[str]:
    parts = re.split(r"[/／]", character)
    return [part.strip() for part in parts if part.strip()]


def _build_character_aliases(
    records: list[Record],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """按 entry 合并 ``A/B`` 形式的同角色别名。"""

    entries: dict[str, dict] = {}
    for record in records:
        entry = entry_group_key(record)
        state = entries.setdefault(
            entry,
            {"parent": {}, "first": {}, "slashes": []},
        )
        for character, _cvs in _parse_role_lines(record.get("role")):
            parts = _split_character_names(character)
            keys = [
                _normalize_name(part)
                for part in parts
                if _normalize_name(part)
            ]
            if not keys:
                continue
            for key, part in zip(keys, parts):
                state["parent"].setdefault(key, key)
                state["first"].setdefault(key, part)
            if len(keys) > 1:
                state["slashes"].append((keys, character))

    aliases: dict[str, dict[str, str]] = {}
    displays: dict[str, dict[str, str]] = {}
    for entry, state in entries.items():
        parent: dict[str, str] = state["parent"]

        def find(name: str) -> str:
            root = name
            while parent[root] != root:
                root = parent[root]
            while parent[name] != name:
                nxt = parent[name]
                parent[name] = root
                name = nxt
            return root

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for keys, _character in state["slashes"]:
            root = find(keys[0])
            for key in keys[1:]:
                union(root, key)

        slash_display: dict[str, str] = {}
        for keys, character in state["slashes"]:
            root = find(keys[0])
            slash_display.setdefault(root, character)

        alias_map: dict[str, str] = {}
        display_map: dict[str, str] = {}
        for key, part in state["first"].items():
            root = find(key)
            alias_map[key] = root
            display_map.setdefault(
                root,
                slash_display.get(root) or part,
            )
        for keys, character in state["slashes"]:
            alias_map[_normalize_name(character)] = find(keys[0])
        aliases[entry] = alias_map
        displays[entry] = display_map
    return aliases, displays


def _collect_roles(
    records: list[Record],
    works: list[dict],
    aliases: dict[str, dict[str, str]],
    displays: dict[str, dict[str, str]],
) -> dict[tuple[str, str], dict]:
    """按 ``(entry, canonical角色)`` 合并所有声优的出场。"""

    groups: dict[tuple[str, str], dict] = {}
    for work_id, record in enumerate(records):
        parsed = _parse_role_lines(record.get("role"))
        total = len(parsed)
        works[work_id]["role_total"] = total
        entry = works[work_id]["entry"]
        for idx, (character, cvs) in enumerate(parsed):
            base = _normalize_name(character)
            canonical = aliases.get(entry, {}).get(base, base)
            display = displays.get(entry, {}).get(canonical, character)
            key = (entry, canonical)
            group = groups.get(key)
            if group is None:
                group = {
                    "entry": entry,
                    "character": display,
                    "appearances": {},
                    "cvs": {},
                }
                groups[key] = group
            previous = group["appearances"].get(work_id)
            if previous is None or idx < previous:
                group["appearances"][work_id] = idx
            for cv in cvs:
                group["cvs"].setdefault(_normalize_name(cv), cv)
    return groups


def _aggregate_roles(
    group: dict,
    works: list[dict],
    entries: dict[str, EntryStats],
    series_count: int,
) -> list[RoleScore]:
    entry = group["entry"]
    stats = entries.get(entry)
    if stats is None:
        return []
    appearances: dict[int, int] = group["appearances"]
    count = len(appearances)

    positions: list[float] = []
    best_work_id: int | None = None
    best_value: float | None = None
    core_role = False
    most_role = False
    for work_id, idx in appearances.items():
        work = works[work_id]
        total = int(work.get("role_total") or 1)
        core_band = (
            _CORE_BAND_BASE + _CORE_BAND_SLOPE * total
        )
        most_band = max(total / 2.0, core_band)
        if idx < core_band:
            core_role = True
        if idx < most_band:
            most_role = True
        position = _position_score(idx, total)
        positions.append(position)
        value = (
            work["rating"]
            if work["rating"] is not None
            else stats.score
        )
        if best_value is None or value > best_value:
            best_value = value
            best_work_id = work_id

    p_pos = sum(positions) / count
    p_stab = (
        1.0 - min(1.0, statistics.pstdev(positions))
        if count >= 2
        else 0.0
    )
    p_rec = count / stats.size
    if p_rec < 0.65:
        p_rec = -2.467 * p_rec**3 - 2.173 * p_rec**2 + 2.838 * p_rec
    else:
        p_rec = 1.0
    p_core = min(1.0, p_rec / _CORE_REC) * min(
        1.0, p_pos / _CORE_POS
    )

    role_ratings = [
        works[work_id]["rating"]
        for work_id in appearances
        if works[work_id]["rating"] is not None
    ]
    role_score = (
        max(role_ratings) if role_ratings else stats.score
    )
    role_q = (role_score / 100.0) ** 4
    role_weight = role_q * stats.episode_factor

    prominence = (
        _POS_WEIGHT * p_pos
        + _REC_WEIGHT * p_rec
        + _CORE_WEIGHT * p_core
        + _STAB_WEIGHT * p_stab
    )
    if _GENERIC_RE.search(group["character"]):
        if core_role:
            pass
        elif most_role:
            prominence *= _GENERIC_PENALTY_MOST
        else:
            prominence *= _GENERIC_PENALTY

    rating_conf = (
        1.0
        if role_ratings
        else (0.6 if series_count else 0.3)
    )
    confidence = (
        0.6 * min(1.0, p_rec / _CONF_REC)
        + 0.2 * min(1.0, count / 3)
        + 0.2 * rating_conf
    )
    score = prominence * role_weight

    best = works[best_work_id] if best_work_id is not None else None
    return [
        RoleScore(
            cv=cv,
            entry=entry,
            character=group["character"],
            score=score,
            confidence=confidence,
            appearances=count,
            entry_size=stats.size,
            position=p_pos,
            recurrence=p_rec,
            core=p_core,
            stability=p_stab,
            series_score=role_score,
            entry_weight=role_weight,
            best_anime=best["anime"] if best else "",
            best_rating=role_score,
            best_year=best["year"] if best else None,
        )
        for cv in group["cvs"].values()
    ]

def _sort_key(role: RoleScore) -> tuple:
    return (
        -role.score,
        -role.entry_weight,
        -role.best_rating,
        -role.appearances,
        role.best_year if role.best_year is not None else 9999,
    )


def _build_cowork(
    records: list[Record],
) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    """按作品构建声优共演稀疏邻接表。"""

    cowork: dict[str, dict[str, int]] = {}
    names: dict[str, str] = {}
    for record in records:
        parsed = _parse_role_lines(record.get("role"))
        work_cvs: dict[str, str] = {}
        for _character, cvs in parsed:
            for cv in cvs:
                key = _normalize_name(cv)
                work_cvs.setdefault(key, cv)
                names.setdefault(key, cv)
                cowork.setdefault(key, {})
        keys = sorted(work_cvs)
        for left, right in combinations(keys, 2):
            cowork.setdefault(left, {})
            cowork.setdefault(right, {})
            cowork[left][right] = cowork[left].get(right, 0) + 1
            cowork[right][left] = cowork[right].get(left, 0) + 1
    return cowork, names


def build_index(
    records: list[Record],
    index_id: int = 0,
) -> PreworkIndex:
    """构建一次完整索引，不修改全局缓存。"""

    works, entry_works = _build_works(records)
    entries, global_mean, series_count = _build_entries(
        works, entry_works
    )
    aliases, displays = _build_character_aliases(records)
    groups = _collect_roles(records, works, aliases, displays)
    roles_by_cv: dict[str, list[RoleScore]] = {}
    for group in groups.values():
        for role in _aggregate_roles(
            group, works, entries, series_count
        ):
            roles_by_cv.setdefault(
                _normalize_name(role.cv), []
            ).append(role)

    roles: dict[str, tuple[RoleScore, ...]] = {}
    for cv_key, scored in roles_by_cv.items():
        scored.sort(key=_sort_key)
        roles[cv_key] = tuple(scored)

    cowork, cowork_names = _build_cowork(records)
    return PreworkIndex(
        index_id=index_id,
        built_at=time.time(),
        entries=entries,
        roles=roles,
        cowork=cowork,
        cowork_names=cowork_names,
        global_mean=global_mean,
        series_count=series_count,
    )


_LOCK = threading.RLock()
_BUILD_LOCK = threading.Lock()
_INDEX: PreworkIndex | None = None
_INDEX_MTIME: int | None = None
_NEXT_INDEX_ID = 0


def _watched_mtime() -> int | None:
    from bangumi.core.storage import table_file

    try:
        return table_file().stat().st_mtime_ns
    except OSError:
        return None


def refresh(records: list[Record]) -> PreworkIndex:
    """用给定记录重建索引，并分配一个新的 ``index_id``。"""

    global _NEXT_INDEX_ID, _INDEX, _INDEX_MTIME

    with _BUILD_LOCK:
        _NEXT_INDEX_ID += 1
        index = build_index(records, _NEXT_INDEX_ID)
        mtime = _watched_mtime()
        with _LOCK:
            _INDEX = index
            _INDEX_MTIME = mtime
    return index


def refresh_from_disk() -> PreworkIndex:
    """从 ``watched.json`` 重新读取并重建索引。"""

    from bangumi.data.watched_data import load_records

    return refresh(load_records())


def invalidate() -> None:
    """丢弃当前索引；下次查询时按需重建。"""

    global _INDEX, _INDEX_MTIME

    with _LOCK:
        _INDEX = None
        _INDEX_MTIME = None


def get_index() -> PreworkIndex | None:
    with _LOCK:
        return _INDEX


def ensure_index(
    records: list[Record] | None = None,
) -> PreworkIndex:
    """返回当前索引；没有时立即构建。"""

    index = get_index()
    if index is not None:
        with _LOCK:
            cached_mtime = _INDEX_MTIME
        if cached_mtime != _watched_mtime():
            return refresh_from_disk()
        return index
    if records is None:
        return refresh_from_disk()
    return refresh(records)


def precompute(records: list[Record] | None = None) -> PreworkIndex:
    """预处理入口：应用启动或 watched.json 变化后调用。"""
    return ensure_index(records)


def cowork_neighbors(cv: str) -> list[tuple[str, int]]:
    index = ensure_index()
    key = _normalize_name(cv)
    items = index.cowork.get(key, {})
    result = [
        (index.cowork_names.get(other, other), count)
        for other, count in items.items()
    ]
    result.sort(key=lambda item: (-item[1], item[0]))
    return result
