"""观影表格的字段结构与持久化。"""

from __future__ import annotations

import re
from bangumi.core.utils import to_bgm_id
from typing import TypeAlias

from bangumi.core.storage import read_json, table_file, write_json

WATCHED_COLUMNS = (
    ("number", "序号"),
    ("anime", "动画"),
    ("specification", "规格"),
    ("category", "类型"),
    ("tag", "TAG"),
    ("author", "作者"),
    ("studio", "制作公司"),
    ("broadcast", "放送"),
    ("role", "角色"),
    ("rating", "评分"),
    ("completion", "补完"),
    ("remark", "备注"),
)
RECORD_FIELDS = tuple(key for key, _ in WATCHED_COLUMNS if key != "number")
HIDDEN_BOOLEAN_FIELDS = ("sequel", "skip_fill")
HIDDEN_STRING_FIELDS = ("entry", "former_name")
HIDDEN_INT_FIELDS = ("bgm_id",)
DETAIL_FIELDS = ("specification", "studio", "broadcast")
STUDIO_SEPARATOR = "×"
AUTHOR_SEPARATOR = "、"
_TAG_SEPARATORS = re.compile(r"[\r\n、,，;；|]+")
_SPEC_PART_SEPARATORS = re.compile(r"[+＋、,，/·|]")
_SPEC_NON_TV_RE = re.compile(r"OVA|OAD|SP", re.IGNORECASE)
_SPEC_EPISODE_RE = re.compile(r"(\d+)\s*(?:话|集)")
_SPEC_BARE_NUMBER_RE = re.compile(r"\d+")


def is_tv_specification(value: str) -> bool:
    """空规格或总集数 ≥2 的规格算 TV；单集、OAD/OVA/SP 不算。"""
    text = str(value or "").strip()
    if not text:
        return True
    total = 0
    found_episode = False
    for raw in _SPEC_PART_SEPARATORS.split(text):
        part = raw.strip()
        if not part:
            continue
        if _SPEC_NON_TV_RE.search(part) or "分钟" in part:
            continue
        matches = list(_SPEC_EPISODE_RE.finditer(part))
        if matches:
            found_episode = True
            total += sum(int(match.group(1)) for match in matches)
            continue
        if _SPEC_BARE_NUMBER_RE.fullmatch(part):
            found_episode = True
            total += int(part)
    return found_episode and total > 1

Record: TypeAlias = dict[str, str | bool | int]


def split_tags(value: str | list | tuple) -> list[str]:
    """拆分 TAG 单元格，保留含空格的标签。"""
    if isinstance(value, (list, tuple)):
        parts = [str(part) for part in value]
    else:
        parts = _TAG_SEPARATORS.split(str(value or ""))

    tags: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tag = part.strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def dedupe_record_tags(records: list[Record]) -> bool:
    changed = False
    for record in records:
        raw = str(record.get("tag") or "")
        tags = split_tags(raw)
        cleaned = "\n".join(tags)
        if cleaned != raw:
            record["tag"] = cleaned
            changed = True
    return changed


def split_studios(value: str) -> list[str]:
    """按乘号拆分制作公司单元格并去重。"""
    studios: list[str] = []
    seen: set[str] = set()
    for part in str(value or "").split(STUDIO_SEPARATOR):
        studio = part.strip()
        if studio and studio not in seen:
            seen.add(studio)
            studios.append(studio)
    return studios


def split_authors(value: str) -> list[str]:
    """按 、/换行拆分作者单元格并去重。"""
    authors: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[、\r\n]+", str(value or "")):
        author = part.strip()
        if author and author not in seen:
            seen.add(author)
            authors.append(author)
    return authors


def record_anime(record: Record) -> str:
    return str(record.get("anime") or "").strip()


def record_entry(record: Record) -> str:
    return str(record.get("entry") or "").strip()


def record_title(record: Record) -> str:
    return record_anime(record) or record_entry(record)


def entry_group_key(record: Record) -> str:
    """返回用于将记录归入同一条目的值。"""
    value = record.get("entry") or record.get("anime") or ""
    return str(value).strip()


def propagate_sequel(
    records: list[Record],
    key: str,
    value: bool,
) -> bool:
    """设置同一条目组内所有记录的续作标记。"""
    if not key:
        return False

    changed = False
    for record in records:
        if entry_group_key(record) != key:
            continue
        if bool(record.get("sequel")) is not value:
            record["sequel"] = value
            changed = True
    return changed


def sync_sequel_groups(records: list[Record]) -> bool:
    """任一条目带续作标记时，标记其全部记录。"""
    groups: dict[str, list[Record]] = {}
    for record in records:
        key = entry_group_key(record)
        if key:
            groups.setdefault(key, []).append(record)

    changed = False
    for group in groups.values():
        if not any(record.get("sequel") is True for record in group):
            continue
        for record in group:
            if record.get("sequel") is not True:
                record["sequel"] = True
                changed = True
    return changed


def group_records_by_studio(
    records: list[Record],
) -> dict[str, list[Record]]:
    """按记录所属的每个制作公司分组，保持原顺序。"""
    groups: dict[str, list[Record]] = {}
    for record in records:
        for studio in split_studios(
            str(record.get("studio", "") or "")
        ):
            groups.setdefault(studio, []).append(record)
    return groups


def load_records() -> list[Record]:
    path = table_file()
    if not path.is_file():
        return []

    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError("Watched 表格文件格式无效")

    records: list[Record] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tag_value = item.get("tag", "")
        if isinstance(tag_value, (list, tuple)):
            tag_value = "\n".join(str(part) for part in tag_value)
        else:
            tag_value = str(tag_value or "")
        record: Record = {
            **{
                field: str(item.get(field, ""))
                for field in RECORD_FIELDS
            },
            **{
                field: item.get(field) is True
                for field in HIDDEN_BOOLEAN_FIELDS
            },
            **{
                field: str(item.get(field) or "")
                for field in HIDDEN_STRING_FIELDS
            },
            **{
                field: to_bgm_id(item.get(field))
                for field in HIDDEN_INT_FIELDS
            },
        }
        record["tag"] = tag_value
        records.append(record)
    return records


def save_records(records: list[Record]) -> None:
    write_json(
        table_file(),
        [
            {
                key: value
                for key, value in record.items()
                if key != "number"
            }
            for record in records
        ],
    )
