# 只导出包外实际使用的名字，避免无意义 re-export。
"""已阅页。"""

from .page import watched_view

__all__ = ["watched_view"]
