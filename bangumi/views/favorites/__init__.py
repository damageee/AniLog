"""收藏板块的公共导出。"""

from bangumi.views.favorites.fav_page import favorite_page_view
from bangumi.views.favorites.page import favorites_view
from bangumi.views.favorites.picker import (
    open_add_to_favorites_dialog,
)

__all__ = [
    "favorite_page_view",
    "favorites_view",
    "open_add_to_favorites_dialog",
]
