"""应用数据导入导出与局域网同步的共享辅助函数。"""

from __future__ import annotations

import base64
import datetime as dt
import hmac
import json
import platform
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Callable

import flet as ft

from bangumi.data.preferences import Preferences
from bangumi.core.storage import storage_directory

APP_VERSION = "0.1.0"
FORMAT_NAME = "anilog-config"
DISCOVERY_PORT = 47823
PROTOCOL_VERSION = 1
PAIR_TTL_SECONDS = 300
SCAN_TIMEOUT = 2.0
NETWORK_TIMEOUT = 10.0
MAX_MESSAGE_BYTES = 32 * 1024 * 1024

COVER_DIRECTORY = "bgm_cover"
_COVER_NAME_RE = re.compile(r"^[0-9]+\.jpg$", re.IGNORECASE)

IMPORT_TYPE_CHECKS: dict[str, type] = {
    "watched.json": list,
    "watchlist.json": dict,
    "preferences.json": dict,
    "watched_preferences.json": dict,
    "watchlist_preferences.json": dict,
    "season.json": dict,
    "bilibili_import.json": dict,
}


class SyncError(Exception):
    """面向用户的局域网同步错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def collect_storage_files(
    directory: Path | None = None,
) -> dict[str, object]:
    """返回存储目录中所有可解析的 ``*.json`` 文件。"""
    root = Path(directory) if directory is not None else storage_directory()
    files: dict[str, object] = {}
    if not root.is_dir():
        return files
    for path in sorted(root.glob("*.json")):
        if not path.is_file():
            continue
        if path.name == "watched_preferences.json":
            continue
        try:
            files[path.name] = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
    return files


def collect_cover_files() -> dict[str, str]:
    from bangumi.data.watched_data import load_records

    try:
        records = load_records()
    except Exception:
        records = []
    subject_ids: set[int] = set()
    for record in records:
        bgm_id = record.get("bgm_id")
        if isinstance(bgm_id, int) and bgm_id != -1:
            subject_ids.add(bgm_id)
    root = storage_directory() / COVER_DIRECTORY
    if not root.is_dir() or not subject_ids:
        return {}
    covers: dict[str, str] = {}
    for subject_id in sorted(subject_ids):
        path = root / f"{subject_id}.jpg"
        if not path.is_file() or not _COVER_NAME_RE.fullmatch(path.name):
            continue
        try:
            covers[path.name] = base64.b64encode(
                path.read_bytes()
            ).decode("ascii")
        except OSError:
            continue
    return covers


def build_export_document(
    files: dict[str, object],
    *,
    exported_at: str | None = None,
) -> dict[str, object]:
    return {
        "format": FORMAT_NAME,
        "version": APP_VERSION,
        "exported_at": (
            exported_at
            or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        "files": files,
    }


def current_export_document(
    include_covers: bool = False,
) -> dict[str, object]:
    document = build_export_document(collect_storage_files())
    if include_covers:
        covers = collect_cover_files()
        if covers:
            document["covers"] = covers
    return document


def export_document_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def validate_export_document(
    document: object,
) -> dict[str, object]:
    """校验导出的配置并返回其安全的文件内容。"""
    if not isinstance(document, dict):
        raise ValueError("配置文件的顶层必须是 JSON 对象")
    if document.get("version") != APP_VERSION:
        raise ValueError("数据与应用版本不匹配")
    if document.get("format") != FORMAT_NAME:
        raise ValueError("这不是 AniLog 应用数据导出文件")
    files = document.get("files")
    if not isinstance(files, dict):
        raise ValueError("配置文件的 files 字段必须是对象")

    validated: dict[str, object] = {}
    for name, value in files.items():
        if not isinstance(name, str):
            raise ValueError("文件名必须是字符串")
        if (
            not name.endswith(".json")
            or name in (".", "..")
            or ".." in name
            or "/" in name
            or "\\" in name
            or Path(name).name != name
        ):
            raise ValueError(f"不安全的文件名：{name}")
        expected = IMPORT_TYPE_CHECKS.get(name)
        if expected is not None and not isinstance(value, expected):
            raise ValueError(
                f"{name} 的内容类型应为 {expected.__name__}"
            )
        validated[name] = value
    return validated


def validate_cover_files(document: object) -> dict[str, str]:
    if not isinstance(document, dict):
        return {}
    covers = document.get("covers")
    if covers is None:
        return {}
    if not isinstance(covers, dict):
        raise ValueError("封面图数据格式无效")
    validated: dict[str, str] = {}
    for name, value in covers.items():
        if not isinstance(name, str) or not _COVER_NAME_RE.fullmatch(name):
            raise ValueError(f"不安全的封面文件名：{name}")
        if not isinstance(value, str):
            raise ValueError("封面图内容必须是 base64 字符串")
        validated[name] = value
    return validated


def apply_import_files(
    directory: Path,
    files: dict[str, object],
) -> None:
    """先暂存所有文件，再原子替换目标。"""
    if (
        "preferences.json" not in files
        and "watched_preferences.json" in files
    ):
        files = dict(files)
        files["preferences.json"] = files.pop(
            "watched_preferences.json"
        )
    directory.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    backups: dict[Path, bytes | None] = {}
    try:
        for name, value in files.items():
            target = directory / name
            temporary = target.with_name(
                target.name + ".import.tmp"
            )
            temporary.write_text(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            staged.append((temporary, target))
        for _, target in staged:
            backups[target] = (
                target.read_bytes() if target.is_file() else None
            )
        for temporary, target in staged:
            temporary.replace(target)
    except OSError:
        for target, data in backups.items():
            try:
                if data is None:
                    if target.exists():
                        target.unlink()
                else:
                    target.write_bytes(data)
            except OSError:
                pass
        raise
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass


def apply_cover_files(covers: dict[str, str]) -> None:
    if not covers:
        return
    directory = storage_directory() / COVER_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in covers.items():
        try:
            raw = base64.b64decode(data, validate=True)
        except Exception:
            continue
        try:
            (directory / name).write_bytes(raw)
        except OSError:
            continue


def apply_export_document(
    document: object,
) -> dict[str, object]:
    """先校验再应用文档；失败时不写入任何内容。"""
    files = validate_export_document(document)
    if (
        "preferences.json" not in files
        and "watched_preferences.json" in files
    ):
        files["preferences.json"] = files.pop(
            "watched_preferences.json"
        )
    covers = validate_cover_files(document)
    apply_import_files(storage_directory(), files)
    apply_cover_files(covers)
    return files


def reload_app(page: ft.Page) -> None:
    """重新加载偏好并重建整个视图栈。"""
    while page.pop_dialog() is not None:
        pass
    preferences = Preferences.load()
    page.theme_mode = (
        ft.ThemeMode.DARK
        if preferences.theme_mode == "dark"
        else ft.ThemeMode.LIGHT
    )
    page.bgcolor = (
        ft.Colors.BLACK
        if preferences.theme_mode == "dark"
        else ft.Colors.WHITE
    )
    page.views.clear()
    if page.on_route_change is not None:
        page.on_route_change(None)
    else:
        page.update()


def device_name() -> str:
    return platform.node() or socket.gethostname() or "AniLog"


def local_ip_addresses() -> list[str]:
    """返回本机的非回环 IPv4 地址。"""
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET
        ):
            address = str(info[4][0])
            if address and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = str(probe.getsockname()[0])
            if address and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def _send_json_line(sock: socket.socket, payload: object) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sock.sendall(data + b"\n")


def _recv_json_line(sock: socket.socket) -> object:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_MESSAGE_BYTES:
            raise SyncError("invalid", "数据过大")
        if b"\n" in chunk:
            break
    raw = b"".join(chunks).split(b"\n", 1)[0]
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise SyncError("invalid", "返回数据不是合法 JSON") from error


def discover_devices(
    timeout: float = SCAN_TIMEOUT,
) -> list[dict[str, object]]:
    """广播 UDP 发现请求并收集活动设备。"""
    request = {
        "anilog": "discover",
        "name": device_name(),
        "protocol": PROTOCOL_VERSION,
    }
    devices: dict[tuple[str, int], dict[str, object]] = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        return []
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.3)
        try:
            sock.sendto(
                json.dumps(request).encode("utf-8"),
                ("255.255.255.255", DISCOVERY_PORT),
            )
        except OSError:
            pass
        deadline = time.monotonic() + max(0.1, timeout)
        while time.monotonic() < deadline:
            try:
                data, address = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("anilog") != "offer":
                continue
            if payload.get("protocol") != PROTOCOL_VERSION:
                continue
            port = payload.get("port")
            if not isinstance(port, int) or not 0 < port < 65536:
                continue
            host = str(address[0])
            name = str(payload.get("name") or host)
            devices[(host, port)] = {
                "name": name,
                "host": host,
                "port": port,
            }
    finally:
        sock.close()
    return sorted(
        devices.values(),
        key=lambda item: (
            str(item["name"]).casefold(),
            str(item["host"]),
            int(item["port"]),
        ),
    )


def pull_document(
    host: str,
    port: int,
    pair: str,
    timeout: float = NETWORK_TIMEOUT,
    *,
    include_covers: bool = False,
) -> dict[str, object]:
    """向设备请求共享文档。"""
    try:
        with socket.create_connection(
            (host, port), timeout=timeout
        ) as connection:
            connection.settimeout(timeout)
            _send_json_line(
                connection,
                {
                    "action": "pull",
                    "pair": pair,
                    "protocol": PROTOCOL_VERSION,
                    "covers": bool(include_covers),
                },
            )
            response = _recv_json_line(connection)
    except socket.timeout as error:
        raise SyncError("timeout", "连接超时") from error
    except OSError as error:
        raise SyncError(
            "connection", f"连接失败：{error}"
        ) from error

    if not isinstance(response, dict):
        raise SyncError("invalid", "对端返回的数据无效")
    if response.get("ok") is not True:
        reason = str(response.get("error") or "invalid")
        if reason == "pair":
            raise SyncError("pair", "配对码错误")
        if reason == "expired":
            raise SyncError("pair", "配对码已过期")
        if reason == "version":
            raise SyncError("version", "版本不匹配")
        raise SyncError("invalid", "对端拒绝了拉取请求")

    document = response.get("document")
    try:
        validate_export_document(document)
    except ValueError as error:
        message = str(error)
        code = "version" if "版本" in message else "invalid"
        raise SyncError(code, message) from error
    return document


class ShareServer:
    """通过 UDP 通告的临时 TCP 数据提供者。"""

    def __init__(
        self,
        document_provider: Callable[
            [], dict[str, object]
        ] = current_export_document,
    ) -> None:
        self.document_provider = document_provider
        self.name = device_name()
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.deadline = time.monotonic() + PAIR_TTL_SECONDS
        self.served = threading.Event()
        self._stop = threading.Event()
        self.tcp_socket: socket.socket | None = None
        self.udp_socket: socket.socket | None = None
        self.port: int | None = None
        self._threads: list[threading.Thread] = []

    def is_running(self) -> bool:
        return not self._stop.is_set()

    def is_expired(self) -> bool:
        return time.monotonic() > self.deadline

    def start(self) -> None:
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp.bind(("0.0.0.0", 0))
        tcp.listen(5)
        tcp.settimeout(0.5)
        self.tcp_socket = tcp
        self.port = tcp.getsockname()[1]

        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            udp.bind(("0.0.0.0", DISCOVERY_PORT))
        except OSError as error:
            tcp.close()
            self.tcp_socket = None
            raise SyncError(
                "connection", f"无法监听发现端口：{error}"
            ) from error
        udp.settimeout(0.5)
        self.udp_socket = udp

        self._threads = [
            threading.Thread(target=self._serve_tcp, daemon=True),
            threading.Thread(target=self._serve_udp, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        for sock in (self.tcp_socket, self.udp_socket):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        self.tcp_socket = None
        self.udp_socket = None
        for thread in self._threads:
            if thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=0.5)

    def _serve_udp(self) -> None:
        while not self._stop.is_set():
            sock = self.udp_socket
            if sock is None:
                break
            try:
                data, address = sock.recvfrom(4096)
            except socket.timeout:
                if self.is_expired():
                    self.stop()
                    break
                continue
            except OSError:
                break
            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("anilog") != "discover":
                continue
            if payload.get("protocol") != PROTOCOL_VERSION:
                continue
            try:
                sock.sendto(
                    json.dumps(
                        {
                            "anilog": "offer",
                            "name": self.name,
                            "port": self.port,
                            "protocol": PROTOCOL_VERSION,
                        }
                    ).encode("utf-8"),
                    address,
                )
            except OSError:
                pass

    def _serve_tcp(self) -> None:
        while not self._stop.is_set():
            sock = self.tcp_socket
            if sock is None:
                break
            try:
                connection, _ = sock.accept()
            except socket.timeout:
                if self.is_expired():
                    self.stop()
                    break
                continue
            except OSError:
                break
            connection.settimeout(NETWORK_TIMEOUT)
            try:
                self._handle(connection)
            finally:
                try:
                    connection.close()
                except OSError:
                    pass
            if self.served.is_set():
                break

    def _handle(self, connection: socket.socket) -> None:
        try:
            request = _recv_json_line(connection)
        except (SyncError, OSError):
            self._reply(connection, {"ok": False, "error": "invalid"})
            return
        if not isinstance(request, dict):
            self._reply(connection, {"ok": False, "error": "invalid"})
            return
        if request.get("protocol") != PROTOCOL_VERSION:
            self._reply(connection, {"ok": False, "error": "version"})
            return
        if self.is_expired():
            self._reply(connection, {"ok": False, "error": "expired"})
            return
        pair = str(request.get("pair") or "")
        if not hmac.compare_digest(pair, self.code):
            self._reply(connection, {"ok": False, "error": "pair"})
            return
        try:
            document = self.document_provider()
            include_covers = request.get("covers") is True
            if include_covers:
                covers = collect_cover_files()
                if covers:
                    document = {**document, "covers": covers}
        except Exception:
            self._reply(connection, {"ok": False, "error": "invalid"})
            return
        self._reply(connection, {"ok": True, "document": document})
        self.served.set()
        self._stop.set()
        for sock in (self.tcp_socket, self.udp_socket):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    @staticmethod
    def _reply(connection: socket.socket, payload: object) -> None:
        try:
            _send_json_line(connection, payload)
        except OSError:
            pass
