"""应用本地存储的路径与 JSON 辅助函数。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bangumi.core.paths import storage_directory


def table_file() -> Path:
    return storage_directory() / "watched.json"


def watchlist_file() -> Path:
    return storage_directory() / "watchlist.json"


def preferences_file() -> Path:
    return storage_directory() / "preferences.json"


def legacy_preferences_file() -> Path:
    return storage_directory() / "watched_preferences.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    """原子写入 JSON，避免崩溃时留下写了一半的文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)
