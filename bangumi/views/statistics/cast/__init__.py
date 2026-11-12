# 只导出包外实际使用的名字，避免无意义 re-export。
"""声优统计子包。"""

from .page import cast_view

__all__ = ["cast_view"]
