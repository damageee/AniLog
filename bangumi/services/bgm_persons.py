"""Fetch and normalize the persons of one Bangumi subject.

Usage:
    python -m bangumi.services.bgm_persons 225604

Only /subjects/{id}/persons is used. 原作 supplies 作者 (falling back to
导演), 动画制作 supplies 制作公司. Network/format problems yield empty
strings, never exceptions.
"""

from __future__ import annotations

import json
import sys

from bangumi.services.bgm_info import API_ROOT, _get_json


def get_persons(subject_id: int | str) -> dict[str, object]:
    """Return {"作者", "制作公司"} for one subject."""
    result: dict[str, object] = {"作者": "", "制作公司": ""}
    try:
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return result
    data = _get_json(f"{API_ROOT}/subjects/{subject_id}/persons")
    persons = data.get("data") if isinstance(data, dict) else data
    if not isinstance(persons, list):
        return result
    authors: list[str] = []
    director = ""
    studios: list[str] = []
    for person in persons:
        if not isinstance(person, dict):
            continue
        relation = str(person.get("relation") or "").strip()
        name = str(person.get("name") or "").strip()
        if not name:
            continue
        if relation == "原作":
            if name not in authors:
                authors.append(name)
        elif relation == "导演" and not director:
            director = name
        elif relation == "动画制作":
            if name not in studios:
                studios.append(name)
    result["作者"] = "、".join(authors) or director
    result["制作公司"] = "×".join(studios)
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        return 1
    try:
        subject_id = int(args[0])
    except ValueError:
        return 1
    print(
        json.dumps(
            get_persons(subject_id),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
