# 只导出包外实际使用的名字，避免无意义 re-export。
"""评分统计子包。"""

from .page import rating_view

__all__ = ["rating_view"]
