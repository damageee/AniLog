"""Fetch and normalize the characters of one Bangumi subject.

Usage:
    python -m bangumi.services.bgm_characters 225604

Only /subjects/{id}/characters is used. Output keeps the previous format:
one "角色(CV)" line per 主角/配角, missing CV shown as "(无)".
"""

from __future__ import annotations

import json
import sys

from bangumi.services.bgm_info import API_ROOT, _get_json


def get_characters(subject_id: int | str) -> dict[str, object]:
    """Return {"角色": "..."} for one subject."""
    result: dict[str, object] = {"角色": ""}
    try:
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return result
    data = _get_json(f"{API_ROOT}/subjects/{subject_id}/characters")
    characters = data.get("data") if isinstance(data, dict) else data
    if not isinstance(characters, list):
        return result
    lines: list[str] = []
    for relation in ("主角", "配角"):
        for character in characters:
            if not isinstance(character, dict):
                continue
            if str(character.get("relation") or "").strip() != relation:
                continue
            name = str(character.get("name") or "").strip()
            name = name.replace("(", "（").replace(")", "）")
            if not name:
                continue
            actors = character.get("actors")
            cv = ""
            if isinstance(actors, list):
                names: list[str] = []
                for actor in actors:
                    if isinstance(actor, dict):
                        actor_name = str(actor.get("name") or "").strip()
                        if actor_name:
                            names.append(actor_name)
                cv = "/".join(names)
            if not cv:
                if relation == "配角":
                    continue
                lines.append(f"{name}(无)")
                continue
            lines.append(f"{name}({cv})")
    result["角色"] = "\n".join(lines)
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
            get_characters(subject_id),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
