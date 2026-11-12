"""已阅页面的表格、分页与筛选常量。"""

from __future__ import annotations


MIN_COLUMN_WIDTH = 48
COLUMN_TEXT_SAFETY_RATIO = 0.02
COLUMN_TEXT_PADDING = 4
PAGE_STEP = 5
DATA_ROW_HEIGHT = 40.0
MIN_TABLE_BODY_HEIGHT = 160.0
TABLE_COLUMN_SPACING = 4.0
TABLE_HORIZONTAL_MARGIN = 24.0
WATCHLIST_FUZZY_MIN = 4
WATCHLIST_FUZZY_RATIO = 0.9
WATCHLIST_LENGTH_RATIO = 0.85
FILTER_MODES = (
    ("category", "按类型"),
    ("tag", "按标签"),
    ("studio", "按制作公司"),
    ("year", "按年份"),
    ("rating", "按评分"),
)
FILTER_RATINGS = ("90+", "80~89", "70~79", "60~69", "50~59", "0~49")
