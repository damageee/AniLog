# 只导出包外实际使用的名字，避免无意义 re-export。
"""设置页。"""

from bangumi.views.settings.page import settings_view

__all__ = ["settings_view"]
