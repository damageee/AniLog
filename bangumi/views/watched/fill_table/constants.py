"""自动填表常量。"""

from __future__ import annotations


IMPORT_LOG_NAME = "import_log.txt"


FILL_FIELDS: tuple[tuple[str, str], ...] = (
    ("specification", "规格"),
    ("category", "类型"),
    ("tag", "TAG"),
    ("author", "作者"),
    ("studio", "制作公司"),
    ("broadcast", "放送"),
    ("role", "角色"),
    ("rating", "评分"),
)


POWER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("always", "一律选用第一符合的"),
    ("precise", "仅自动导入很准确的"),
    ("confident", "仅自动导入有把握的"),
    ("fairly", "仅自动导入较有把握"),
    ("loose", "不是太离谱都自动导入"),
)


INTRO_LINES = (
    "此操作将从Bangumi网站自动搜索并导入动画信息，需要花费一定时间。",
    "为减少导入时间和成本，不会详细获取搜索到的相关动画的详情、别名等",
    "容易导致获取的条目不准确，请结束后仔细检查。",
    "对于把握不大的动画，我将在最后一一询问你。",
)


