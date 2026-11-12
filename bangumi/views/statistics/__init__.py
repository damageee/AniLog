# 只导出包外实际使用的名字，避免无意义 re-export。
"""统计页面包。

common/shared.py            通用工具、样式辅助与布局常量。
common/overlays.py          浮层、引用气泡与定位辅助。
纯数据计算见 bangumi/data/statistics/。
page.py                    统计主页。
overview.py                统计总览页。
journey.py                 旅途（补完曲线/日历）页。
tags.py                    标签统计页。
best_records.py            纪录页。
data_check.py               数据质量检查页。
broadcast/                 放送统计（page / year / quarter / year_quarter）。
studios/                   制作公司（page / search / honor / scatter / homepage）。
cast/                      声优（page / search / detail）。
rating/                    评分（view）。
"""

from bangumi.views.statistics.page import (
    statistics_view,
)
from bangumi.views.statistics.journey import (
    open_month_completion,
)
from bangumi.views.statistics.studios.homepage import (
    open_studio_page,
)

__all__ = [
    "open_month_completion",
    "open_studio_page",
    "statistics_view",
]
