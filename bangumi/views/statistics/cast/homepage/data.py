"""声优主页共享的数据查找辅助。"""

from __future__ import annotations

from bangumi.data import prework
from bangumi.data.quarter_core import earliest_broadcast_date
from bangumi.data.watched_data import Record, entry_group_key


def _record_year(record: Record) -> int | None:
    date = earliest_broadcast_date(
        str(record.get("broadcast") or "")
    )
    return date[0] if date is not None else None


def cast_works(
    records: list[Record],
    cast: str,
) -> list[tuple[Record, list[str]]]:
    """返回该声优参与的作品及其配过的角色名。"""

    key = prework._normalize_name(cast)
    result: list[tuple[Record, list[str]]] = []
    for record in records:
        parsed = prework._parse_role_lines(record.get("role"))
        names: list[str] = []
        for character, cvs in parsed:
            if any(prework._normalize_name(cv) == key for cv in cvs):
                name = character.strip()
                if name and name not in names:
                    names.append(name)
        if names:
            result.append((record, names))
    return result


def role_record(
    records: list[Record],
    role: prework.RoleScore,
) -> Record | None:
    """找到代表角色对应的动画记录。"""

    best = str(role.best_anime or "").strip()
    if best:
        for record in records:
            if str(record.get("anime") or "").strip() == best:
                return record
    for record in records:
        if entry_group_key(record) == role.entry:
            return record
    return None


def _role_key(
    role: prework.RoleScore,
    aliases: dict[str, dict[str, str]],
) -> tuple[str, str]:
    entry = role.entry
    alias_map = aliases.get(entry, {})
    canonical = alias_map.get(prework._normalize_name(role.character))
    if canonical is None:
        parts = prework._split_character_names(role.character)
        if parts:
            canonical = alias_map.get(
                prework._normalize_name(parts[0])
            )
    return (
        entry,
        canonical or prework._normalize_name(role.character),
    )


def series_roles(
    records: list[Record],
    cast: str,
) -> list[tuple[str, list[str], float, prework.RoleScore]]:
    """把该声优的角色按系列合并。"""

    index = prework.ensure_index(records)
    roles = index.roles.get(prework._normalize_name(cast), ())
    grouped: dict[str, dict] = {}
    for role in roles:
        item = grouped.get(role.entry)
        if item is None:
            item = {
                "names": [],
                "score": role.score,
                "role": role,
            }
            grouped[role.entry] = item
        if role.character not in item["names"]:
            item["names"].append(role.character)
        if role.score > item["score"]:
            item["score"] = role.score
            item["role"] = role
    result = [
        (
            entry,
            item["names"],
            item["score"],
            item["role"],
        )
        for entry, item in grouped.items()
    ]
    result.sort(key=lambda item: (-item[2], item[0]))
    return result


def roles_for_year(
    records: list[Record],
    cast: str,
    year: int,
) -> list[prework.RoleScore]:
    """返回该声优在指定年份有出场的角色。"""

    key = prework._normalize_name(cast)
    index = prework.ensure_index(records)
    scored = index.roles.get(key, ())
    if not scored:
        return []
    aliases, _displays = prework._build_character_aliases(records)
    role_by_key = {
        _role_key(role, aliases): role for role in scored
    }

    wanted: set[tuple[str, str]] = set()
    for record in records:
        if _record_year(record) != year:
            continue
        parsed = prework._parse_role_lines(record.get("role"))
        if not any(
            prework._normalize_name(cv) == key
            for _character, cvs in parsed
            for cv in cvs
        ):
            continue
        entry = entry_group_key(record)
        alias_map = aliases.get(entry, {})
        for character, cvs in parsed:
            if not any(
                prework._normalize_name(cv) == key
                for cv in cvs
            ):
                continue
            base = prework._normalize_name(character)
            canonical = alias_map.get(base, base)
            wanted.add((entry, canonical))

    return [
        role
        for role in scored
        if _role_key(role, aliases) in wanted
    ]
