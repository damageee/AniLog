"""观影表格的字段结构与持久化。"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from bangumi.core.utils import to_bgm_id
from typing import TypeAlias

from bangumi.core.storage import read_json, table_file, write_json
from bangumi.data.dates import (
    normalize_broadcast,
    normalize_completion,
)

WATCHED_COLUMNS = (
    ("number", "序号"),
    ("anime", "动画"),
    ("specification", "规格"),
    ("category", "类型"),
    ("tag", "TAG"),
    ("staff", "STAFF"),
    ("studio", "制作公司"),
    ("broadcast", "放送"),
    ("role", "角色"),
    ("rating", "评分"),
    ("completion", "补完"),
    ("remark", "备注"),
)
RECORD_FIELDS = tuple(key for key, _ in WATCHED_COLUMNS if key != "number")
HIDDEN_BOOLEAN_FIELDS = ("sequel", "skip_fill")
HIDDEN_STRING_FIELDS = ("entry", "former_name", "uid")
HIDDEN_INT_FIELDS = ("bgm_id",)
DETAIL_FIELDS = ("specification", "studio", "broadcast")
STUDIO_SEPARATOR = "×"
STAFF_SEPARATOR = "、"
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

Record: TypeAlias = dict[
    str,
    str | bool | int | dict[str, str],
]

STAFF_PRIORITY = ("原作", "总导演", "系列监督", "导演", "脚本")

STAFF_ORDER = (
    "原作",
    "原作协力",
    "原案",
    "总导演",
    "导演",
    "副导演",
    "动画导演",
    "主演出",
    "系列构成",
    "构成协力",
    "系列监督",
    "脚本",
    "脚本协力",
    "分镜",
    "分镜协力",
    "分镜抄写",
    "演出",
    "演出助理",
    "Live 分镜演出",
    "Bank 分镜演出",
    "转场绘",
    "人物原案",
    "人物设定",
    "副人物设定",
    "客座人物设定",
    "机械设定",
    "背景设定",
    "画面设计",
    "概念设计",
    "道具设计",
    "服装设计",
    "标题设计",
    "怪物设计",
    "设定",
    "设定协力",
    "概念艺术",
    "色彩脚本",
    "总作画监督",
    "总作画监督助理",
    "印象板",
    "作画监督",
    "作画监修",
    "作画监督助理",
    "角色作画监督",
    "构图作画监督",
    "机械作画监督",
    "动作作画监督",
    "特效作画监督",
    "道具作画监督",
    "构图监修",
    "主动画师",
    "原画",
    "第二原画",
    "动画检查",
    "补间动画",
    "动作导演",
    "特技导演",
    "视觉概念",
    "插画",
    "剧中剧人设",
    "剧中剧分镜演出",
    "监修",
    "构图",
    "创意总监",
    "视觉导演",
    "技术导演",
    "数码绘图",
    "色彩设计",
    "色彩设计助理",
    "色彩指定",
    "色彩检查",
    "上色检查",
    "上色",
    "特效",
    "美术监督",
    "美术监督助理",
    "美术",
    "美术板",
    "美术设计",
    "背景美术",
    "摄影监督",
    "摄影监督助理",
    "摄影",
    "视觉效果",
    "CG 导演",
    "CG 导演助理",
    "CG 制作人",
    "3DCG",
    "3DCG 导演",
    "3DCG 导演助理",
    "建模/模型",
    "2D 设计",
    "3D 设计",
    "3D 动画师",
    "剪辑",
    "剪辑助理",
    "离线剪辑",
    "在线剪辑",
    "演员监督",
    "音响监督",
    "音响",
    "音响制作担当",
    "音响制作人",
    "音效",
    "选曲",
    "录音工作室",
    "录音",
    "录音助理",
    "整音",
    "音乐",
    "音乐助理",
    "音乐监督",
    "音乐制作人",
    "音乐制作",
    "主题歌作词",
    "主题歌作曲",
    "主题歌编曲",
    "主题歌演出",
    "插入歌作词",
    "插入歌作曲",
    "插入歌编曲",
    "插入歌演出",
    "OP・ED 分镜",
    "OP・ED 演出",
    "OP・ED 动画制作",
    "制作协力",
    "制作统括",
    "现场制片人",
    "动画制片人",
    "制作制片人",
    "制作管理",
    "制作管理助理",
    "制作助理",
    "设定制作",
    "设定制作助理",
    "副制片人",
    "文艺制作",
    "制作事务",
    "制作进行",
    "制作进行协力",
    "美术制作进行",
    "CG 制作进行",
    "总制片人",
    "执行制片人",
    "制片人",
    "联合制片人",
    "制作协调",
    "助理制片人",
    "宣传制片人",
    "企划制作人",
    "创意制片人",
    "宣传",
    "宣传协力",
    "后期制片协调",
    "企画",
    "监制",
    "制作",
    "製作",
    "製作协力",
    "製作统括",
    "发行",
    "协力",
    "企画协力",
    "特别鸣谢",
)


def normalize_staff(value: object) -> dict[str, str]:
    """把 STAFF 统一为 {键: 值}，丢弃空键值与空文本。"""
    if isinstance(value, dict):
        result: dict[str, str] = {}
        for key, item in value.items():
            name = str(key or "").strip()
            text = str(item or "").strip()
            if name and text:
                result[name] = text
        return result
    text = str(value or "").strip()
    return {"原作": text} if text else {}


def staff_display(record: Record) -> str:
    """按优先级返回 STAFF 显示文本。"""
    staff = normalize_staff(record.get("staff"))
    for key in STAFF_PRIORITY:
        value = staff.get(key, "")
        if value:
            return value
    for value in staff.values():
        if value:
            return value
    return ""


def staff_items(staff: object) -> list[tuple[str, str]]:
    """按固定职务顺序返回 (键, 值) 列表。"""
    data = normalize_staff(staff)
    order_index = {
        name: index for index, name in enumerate(STAFF_ORDER)
    }
    special_anchor = float(
        order_index.get("特效作画监督", len(STAFF_ORDER))
    )

    def sort_key(item: tuple[str, str]) -> tuple:
        key = item[0]
        index = order_index.get(key)
        if index is not None:
            return (0, float(index), key)
        # 其它作画监督排在特效作画监督之后、构图监修之前。
        if key.endswith("作画监督"):
            return (0, special_anchor + 0.5, key)
        # 未知职务排在最后，按名称排序。
        return (2, 0.0, key.casefold())

    return sorted(data.items(), key=sort_key)


def staff_lines(record: Record) -> str:
    """每行「键：值」，用于导出与多行显示。"""
    staff = normalize_staff(record.get("staff"))
    return "\n".join(
        f"{key}：{value}" for key, value in staff.items()
    )


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


def _ensure_record_uids(records: list[Record]) -> bool:
    """为缺失或重复的 uid 生成新值，返回是否有改动。"""
    used: set[str] = set()
    changed = False
    for record in records:
        uid = str(record.get("uid") or "").strip()
        if not uid or uid in used:
            uid = uuid.uuid4().hex
            record["uid"] = uid
            changed = True
        used.add(uid)
    return changed


def _backup_watched_file(path: Path) -> None:
    """首次规范化前备份；已有 .bak 则不覆盖。"""
    backup = path.parent / (path.name + ".bak")
    if backup.exists() or not path.is_file():
        return
    try:
        shutil.copy2(path, backup)
    except Exception:
        pass


def load_records() -> list[Record]:
    path = table_file()
    if not path.is_file():
        return []

    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError("Watched 表格文件格式无效")

    records: list[Record] = []
    migrated = False
    ordering_changed = False
    broadcast_changed = False
    completion_changed = False
    text_fields = tuple(
        field for field in RECORD_FIELDS if field != "staff"
    )
    for item in data:
        if not isinstance(item, dict):
            continue
        tag_value = item.get("tag", "")
        if isinstance(tag_value, (list, tuple)):
            tag_value = "\n".join(str(part) for part in tag_value)
        else:
            tag_value = str(tag_value or "")
        raw_staff = item.get("staff")
        if isinstance(raw_staff, dict) or str(
            raw_staff or ""
        ).strip():
            staff = normalize_staff(raw_staff)
        else:
            legacy = str(item.get("author") or "").strip()
            if legacy:
                staff = {"原作": legacy}
                migrated = True
            else:
                staff = {}
        record: Record = {
            **{
                field: str(item.get(field, ""))
                for field in text_fields
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
        # 按 STAFF_ORDER 重排 staff 键顺序；顺序不同才回写。
        ordered = dict(staff_items(staff))
        if list(ordered.keys()) != list(staff.keys()):
            record["staff"] = ordered
            ordering_changed = True
        else:
            record["staff"] = staff
        record["tag"] = tag_value
        raw_broadcast = record.get("broadcast", "")
        new_broadcast = normalize_broadcast(raw_broadcast)
        if new_broadcast != raw_broadcast:
            record["broadcast"] = new_broadcast
            broadcast_changed = True
        raw_completion = record.get("completion", "")
        new_completion = normalize_completion(raw_completion)
        if new_completion != raw_completion:
            record["completion"] = new_completion
            completion_changed = True
        records.append(record)
    # 旧数据缺 uid、author 迁移、staff 顺序或日期规范化时回写一次。
    if (
        _ensure_record_uids(records)
        or migrated
        or ordering_changed
        or broadcast_changed
        or completion_changed
    ):
        if broadcast_changed or completion_changed:
            _backup_watched_file(path)
        try:
            save_records(records)
        except Exception:
            pass
    return records


def save_records(records: list[Record]) -> None:
    # 为缺失或重复的 uid 补一个随机唯一标识。
    _ensure_record_uids(records)
    for record in records:
        record["staff"] = normalize_staff(record.get("staff"))
        record.pop("author", None)
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
    try:
        from bangumi.data import prework

        # 只失效索引，等真正需要统计数据时再按 mtime 重建。
        prework.invalidate()
    except Exception:
        pass
