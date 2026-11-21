# 只导出包外实际使用的名字，避免无意义 re-export。
"""导航与详情页维度再导出。"""

from bangumi.views.navigation.stack import (
    go_back,
    push_view,
)
from bangumi.views.navigation.detail import open_detail
from bangumi.views.navigation.detail_kinds import (
    BROADCAST,
    CAST,
    CATEGORY,
    DETAIL_FIELDS,
    ENTRY,
    ROLE,
    QUARTER_WORKS,
    REMARK,
    STUDIO,
    TAG,
    DetailKind,
)

__all__ = [
    "BROADCAST",
    "CAST",
    "CATEGORY",
    "DETAIL_FIELDS",
    "DetailKind",
    "ENTRY",
    "ROLE",
    "QUARTER_WORKS",
    "REMARK",
    "STUDIO",
    "TAG",
    "go_back",
    "open_detail",
    "push_view",
]
