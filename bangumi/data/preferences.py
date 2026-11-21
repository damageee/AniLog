"""跨会话持久化的用户偏好。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import date
from typing import Any

from bangumi.core.storage import (
    legacy_preferences_file,
    preferences_file,
    read_json,
    write_json,
)
from bangumi.ui.tag_colors import is_valid_color
from bangumi.data.watched_data import WATCHED_COLUMNS

COLUMN_KEYS = [key for key, _ in WATCHED_COLUMNS]
FIXED_COLUMN_KEYS = (
    "anime",
    "specification",
    "category",
    "tag",
    "staff",
    "studio",
    "broadcast",
    "role",
    "rating",
)
THEME_MODES = ("light", "dark")
ANIMATION_MODES = ("full", "off")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass
class Preferences:
    highlight_public_sequels: bool = True
    page_size: int = DEFAULT_PAGE_SIZE
    theme_mode: str = "light"
    animation_mode: str = "full"
    sort_column: str = ""
    sort_ascending: bool = False
    tag_colors: dict[str, str] = field(default_factory=dict)
    tag_color_version: int = 0
    fixed_columns: list[str] = field(default_factory=list)
    special_completion_dates: list[str] = field(
        default_factory=list
    )
    clear_fixed_fields_on_id_import: bool = False
    detail_show_rating: bool = True
    detail_show_completion: bool = True
    detail_show_remark: bool = True
    bilibili_uid: str = ""

    @classmethod
    def load(cls) -> Preferences:
        preferences = cls()
        path = preferences_file()
        legacy = legacy_preferences_file()
        if path.is_file():
            source = path
        elif legacy.is_file():
            source = legacy
        else:
            return preferences

        try:
            saved = read_json(source)
        except (OSError, ValueError):
            return preferences
        if isinstance(saved, dict):
            preferences._apply_saved(saved)
            # 旧 JSON 里有已删除字段时，读完后重写一次清理冗余键。
            known = {
                item.name for item in fields(type(preferences))
            }
            if any(key not in known for key in saved):
                try:
                    preferences.save()
                except OSError:
                    pass
        if source == legacy:
            try:
                preferences.save()
                legacy.unlink(missing_ok=True)
            except OSError:
                pass
        # ===== 旧 bilibili_import.json 迁移 =====
        if not preferences.bilibili_uid:
            old_path = None
            old_data = None
            try:
                from bangumi.views.watchlist.utils import (
                    bilibili_import_file,
                )

                old_path = bilibili_import_file()
                if old_path.is_file():
                    old_data = read_json(old_path)
            except Exception:
                old_path = None
                old_data = None
            if isinstance(old_data, dict):
                uid = str(old_data.get("uid") or "").strip()
                if uid.isdigit():
                    preferences.bilibili_uid = uid
                    try:
                        preferences.save()
                    except OSError:
                        pass
            # 读取后删除旧文件（无效文件也一并清理）。
            if old_path is not None:
                try:
                    old_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return preferences

    @classmethod
    def migrate_legacy_bilibili_uid(cls) -> None:
        """若缺少 UID，尝试从旧 bilibili_import.json 迁移（幂等）。"""
        try:
            cls.load()
        except Exception:
            pass

    def save(self) -> None:
        write_json(preferences_file(), asdict(self))

    def reset(self, *, keep_theme: bool = True) -> None:
        theme_mode = self.theme_mode
        defaults = type(self)()
        self.__dict__.update(defaults.__dict__)
        if keep_theme:
            self.theme_mode = theme_mode

    def _apply_saved(self, saved: dict[str, Any]) -> None:
        self.highlight_public_sequels = bool(
            saved.get("highlight_public_sequels", self.highlight_public_sequels)
        )
        self.bilibili_uid = str(
            saved.get("bilibili_uid", self.bilibili_uid) or ""
        ).strip()

        try:
            page_size = int(saved.get("page_size", self.page_size))
        except (TypeError, ValueError):
            page_size = DEFAULT_PAGE_SIZE
        self.page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        theme_mode = saved.get("theme_mode", self.theme_mode)
        self.theme_mode = theme_mode if theme_mode in THEME_MODES else "light"

        animation_mode = saved.get(
            "animation_mode",
            self.animation_mode,
        )
        if animation_mode == "full":
            self.animation_mode = "full"
        elif animation_mode in ("entry_off", "all_off"):
            self.animation_mode = "off"
        else:
            self.animation_mode = "full"

        sort_column = saved.get("sort_column")
        if sort_column == "author":
            sort_column = "staff"
        if (
            isinstance(sort_column, str)
            and sort_column in COLUMN_KEYS
            and sort_column != "number"
        ):
            self.sort_column = sort_column
        self.sort_ascending = bool(
            saved.get("sort_ascending", self.sort_ascending)
        )

        saved_tag_colors = saved.get("tag_colors")
        if isinstance(saved_tag_colors, dict):
            self.tag_colors = {
                tag: color.upper()
                for tag, color in saved_tag_colors.items()
                if isinstance(tag, str)
                and tag
                and is_valid_color(color)
            }

        try:
            version = int(
                saved.get(
                    "tag_color_version",
                    self.tag_color_version,
                )
            )
        except (TypeError, ValueError):
            version = 0
        self.tag_color_version = max(version, 0)

        saved_fixed = saved.get("fixed_columns")
        if isinstance(saved_fixed, list):
            self.fixed_columns = list(
                dict.fromkeys(
                    key
                    for key in saved_fixed
                    if isinstance(key, str)
                    and key in FIXED_COLUMN_KEYS
                )
            )

        self.clear_fixed_fields_on_id_import = bool(
            saved.get(
                "clear_fixed_fields_on_id_import",
                self.clear_fixed_fields_on_id_import,
            )
        )
        self.detail_show_rating = bool(
            saved.get(
                "detail_show_rating",
                self.detail_show_rating,
            )
        )
        self.detail_show_completion = bool(
            saved.get(
                "detail_show_completion",
                self.detail_show_completion,
            )
        )
        self.detail_show_remark = bool(
            saved.get(
                "detail_show_remark",
                self.detail_show_remark,
            )
        )

        saved_dates = saved.get("special_completion_dates")
        if isinstance(saved_dates, list):
            valid_dates: set[str] = set()
            for value in saved_dates:
                if not isinstance(value, str):
                    continue
                try:
                    parsed = date.fromisoformat(value)
                except ValueError:
                    continue
                if parsed.isoformat() == value:
                    valid_dates.add(value)
            self.special_completion_dates = sorted(valid_dates)
