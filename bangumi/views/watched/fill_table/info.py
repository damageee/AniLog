"""获取条目详情（按需调用三个接口）。"""

from __future__ import annotations

from bangumi.services.bgm_characters import get_characters
from bangumi.services.bgm_info import get_subject_info
from bangumi.services.bgm_persons import get_persons
from bangumi.views.watched.fill_table.fields import needed_keys

BASE_KEYS = frozenset({"规格", "类型", "TAG", "放送", "评分"})
PERSON_KEYS = frozenset({"STAFF", "制作公司"})


def fetch_subject_info(
    anime,
    bgm_id,
    record=None,
    fixed=frozenset(),
    force=False,
) -> dict:
    """仅调用字段确实缺失的接口。"""
    if record is None:
        need = None
    else:
        need = set(needed_keys(record, set(fixed), force))
    info: dict[str, object] = {}
    if need is None or need & BASE_KEYS:
        info.update(get_subject_info(bgm_id, anime))
        if str(info.get("error") or "").strip():
            return info
    if need is None or need & PERSON_KEYS:
        info.update(get_persons(bgm_id))
    if need is None or "角色" in need:
        info.update(get_characters(bgm_id))
    return info
