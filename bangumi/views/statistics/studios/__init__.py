# 只导出包外实际使用的名字，避免无意义 re-export。
"""制作公司统计子包。"""

from .page import studios_view

__all__ = ["studios_view"]
