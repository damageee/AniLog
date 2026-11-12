# 只导出包外实际使用的名字，避免无意义 re-export。
"""已追页。"""

from bangumi.views.watchlist.page import watchlist_view

__all__ = ["watchlist_view"]
