"""导入日志。"""

from __future__ import annotations

from pathlib import Path

from bangumi.core.storage import storage_directory
from bangumi.views.watched.fill_table.constants import IMPORT_LOG_NAME


def _log_path() -> Path:
    return storage_directory() / IMPORT_LOG_NAME


def reset_log() -> None:
    try:
        _log_path().write_text("", encoding="utf-8")
    except OSError:
        pass


def append_log(line: str) -> None:
    try:
        with _log_path().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _failure_detail(
    anime: str,
    module: str,
    reason: str,
    *,
    bgm_id: object = None,
    name_cn: object = "",
) -> str:
    parts: list[str] = []
    if isinstance(bgm_id, int) and bgm_id != -1:
        parts.append(f"bgm_id={bgm_id}")
    name = str(name_cn or "").strip()
    if name:
        parts.append(f"name_cn={name}")
    suffix = f" {' '.join(parts)}" if parts else ""
    return f"原文：{anime} 模块：{module} 原因：{reason}{suffix}"


def log_failure(
    anime: str,
    module: str,
    reason: str,
    *,
    bgm_id: object = None,
    name_cn: object = "",
) -> str:
    detail = _failure_detail(
        anime,
        module,
        reason,
        bgm_id=bgm_id,
        name_cn=name_cn,
    )
    append_log(f"[失败] {detail}")
    return detail


