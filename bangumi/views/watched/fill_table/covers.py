"""封面图。"""

from __future__ import annotations

from pathlib import Path

from bangumi.services.bgm_pic import save_subject_image
from bangumi.views.watched.fill_table.fields import has_cover


def fetch_cover(bgm_id) -> Path | None:
    return save_subject_image(bgm_id)


def cover_exists(record) -> bool:
    return has_cover(record)
