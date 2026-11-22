"""应用版本与数据格式版本。"""

from __future__ import annotations

APP_VERSION = "0.2.1"
APP_VERSION_LABEL = "v2.1"
# 同步/导出数据格式版本；只有数据结构变化时才修改。
DATA_VERSION = 1
# 旧客户端认识的 version 字段。
WIRE_VERSION = "0.2.0"
COMPAT_VERSIONS = ("0.2.0", "0.2.1")
