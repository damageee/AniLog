# 只导出包外实际使用的名字，避免无意义 re-export。
"""制作公司详情主页子包。"""

from .page import open_studio_page

__all__ = ["open_studio_page"]
