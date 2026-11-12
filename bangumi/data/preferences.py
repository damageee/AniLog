"""跨会话持久化的用户偏好。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
DATA_COLUMN_KEYS = [key for key in COLUMN_KEYS if key != "number"]
FIXED_COLUMN_KEYS = (
    "anime",
    "specification",
    "category",
    "tag",
    "author",
    "studio",
    "broadcast",
    "role",
    "rating",
)
THEME_MODES = ("light", "dark")
ANIMATION_MODES = ("full", "off")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _default_visible_columns() -> dict[str, bool]:
    return {key: True for key in COLUMN_KEYS}


@dataclass
class Preferences:
    merge_same_anime: bool = False
    highlight_public_sequels: bool = True
    page_size: int = DEFAULT_PAGE_SIZE
    theme_mode: str = "light"
    animation_mode: str = "full"
    column_order: list[str] = field(default_factory=lambda: list(COLUMN_KEYS))
    sort_column: str = ""
    sort_ascending: bool = False
    visible_columns: dict[str, bool] = field(
        default_factory=_default_visible_columns
    )
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
        if source == legacy:
            try:
                preferences.save()
                legacy.unlink(missing_ok=True)
            except OSError:
                pass
        return preferences

    def save(self) -> None:
        write_json(preferences_file(), asdict(self))

    def reset(self, *, keep_theme: bool = True) -> None:
        theme_mode = self.theme_mode
        defaults = type(self)()
        self.__dict__.update(defaults.__dict__)
        if keep_theme:
            self.theme_mode = theme_mode

    def _apply_saved(self, saved: dict[str, Any]) -> None:
        self.merge_same_anime = bool(
            saved.get("merge_same_anime", self.merge_same_anime)
        )
        self.highlight_public_sequels = bool(
            saved.get("highlight_public_sequels", self.highlight_public_sequels)
        )

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

        saved_order = saved.get("column_order")
        if isinstance(saved_order, list):
            # `number` 为派生列，始终位于首位且不可重排。
            saved_data_columns = list(
                dict.fromkeys(
                    key
                    for key in saved_order
                    if key in DATA_COLUMN_KEYS
                )
            )
            self.column_order = [
                "number",
                *saved_data_columns,
                *(
                    key
                    for key in DATA_COLUMN_KEYS
                    if key not in saved_data_columns
                ),
            ]

        sort_column = saved.get("sort_column")
        if (
            isinstance(sort_column, str)
            and sort_column in COLUMN_KEYS
            and sort_column != "number"
        ):
            self.sort_column = sort_column
        self.sort_ascending = bool(
            saved.get("sort_ascending", self.sort_ascending)
        )

        saved_visible = saved.get("visible_columns")
        if isinstance(saved_visible, dict):
            for key in self.visible_columns:
                if key in saved_visible:
                    self.visible_columns[key] = bool(saved_visible[key])

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
