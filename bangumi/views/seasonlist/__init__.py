# 只导出包外实际使用的名字，避免无意义 re-export。
"""追季页。"""

from .page import season_view

__all__ = ["season_view"]
