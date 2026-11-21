"""获取并规范化某个 Bangumi 条目的制作人员。

用法：
    python -m bangumi.services.bgm_persons 225604

仅使用 /subjects/{id}/persons。除动画制作外的关系归入 STAFF
（关系 -> 姓名列表），动画制作关系提供制作公司。网络/格式问题
返回空结构，不抛异常。
"""

from __future__ import annotations

import json
import sys

from bangumi.services.bgm_info import API_ROOT, _get_json


def get_persons(subject_id: int | str) -> dict[str, object]:
    """Return {"STAFF": {关系: 姓名}, "制作公司": 文本}."""
    result: dict[str, object] = {"STAFF": {}, "制作公司": ""}
    try:
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return result
    data = _get_json(f"{API_ROOT}/subjects/{subject_id}/persons")
    persons = data.get("data") if isinstance(data, dict) else data
    if not isinstance(persons, list):
        return result
    staff: dict[str, list[str]] = {}
    studios: list[str] = []
    for person in persons:
        if not isinstance(person, dict):
            continue
        relation = str(person.get("relation") or "").strip()
        name = str(person.get("name") or "").strip()
        if not relation or not name:
            continue
        if relation == "动画制作":
            if name not in studios:
                studios.append(name)
            continue
        names = staff.setdefault(relation, [])
        if name not in names:
            names.append(name)
    joined = {
        key: "、".join(names)
        for key, names in staff.items()
        if names
    }
    from bangumi.data.watched_data import staff_items

    ordered = staff_items(joined)
    result["STAFF"] = {key: value for key, value in ordered}
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
