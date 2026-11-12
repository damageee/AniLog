# 只导出包外实际使用的名字，避免无意义 re-export。
"""公共视图工厂、详情链接与页面目录。"""

from bangumi.views.home import home_view
from bangumi.views.statistics import statistics_view
from bangumi.views.seasonlist import season_view
from bangumi.views.settings import settings_view
from bangumi.views.watched import watched_view
from bangumi.views.watchlist import watchlist_view

__all__ = [
    "home_view",
    "season_view",
    "settings_view",
    "statistics_view",
    "watched_view",
    "watchlist_view",
]
