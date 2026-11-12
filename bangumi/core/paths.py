"""源码运行与冻结构建均可用的路径解析。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """从源码运行时的仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def app_directory() -> Path:
    """存放 exe 的目录（冻结构建）或项目根目录（源码运行）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def resource_root() -> Path:
    """随包只读资源（assets）的根目录。"""
    if is_frozen():
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            return Path(bundle)
    return project_root()


def assets_directory() -> Path:
    configured = os.environ.get("FLET_ASSETS_DIR")
    if configured:
        return Path(configured)
    return resource_root() / "assets"


def storage_directory() -> Path:
    """可写数据目录：优先 Flet 目录；冻结构建时用 exe 目录，否则用项目目录。"""
    configured = os.environ.get("FLET_APP_STORAGE_DATA")
    if configured:
        return Path(configured)
    if is_frozen():
        return app_directory() / "storage"
    return project_root() / "storage"
