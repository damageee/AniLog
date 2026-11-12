"""catalog、links 与 builder 共用的详情页维度。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetailKind:
    key: str
    label: str


ENTRY = DetailKind("entry", "条目")
CATEGORY = DetailKind("category", "类型")
AUTHOR = DetailKind("author", "作者")
STUDIO = DetailKind("studio", "制作公司")
BROADCAST = DetailKind("broadcast", "发布日")
QUARTER = DetailKind("quarter", "年×季度")
QUARTER_WORKS = DetailKind("quarter_works", "季度作品")
ROLE = DetailKind("role", "角色")
CAST = DetailKind("cast", "声优")
REMARK = DetailKind("remark", "备注")
TAG = DetailKind("tag", "TAG")

DETAIL_FIELDS: dict[DetailKind, str] = {
    ENTRY: "anime",
    CATEGORY: "category",
    AUTHOR: "author",
    STUDIO: "studio",
    BROADCAST: "broadcast",
    QUARTER: "broadcast",
    QUARTER_WORKS: "broadcast",
    ROLE: "role",
    CAST: "cast",
    REMARK: "remark",
    TAG: "tag",
}
