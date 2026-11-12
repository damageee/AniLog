# 只导出包外实际使用的名字，避免无意义 re-export。
"""放送统计子包。"""

from .page import broadcast_view

__all__ = ["broadcast_view"]
