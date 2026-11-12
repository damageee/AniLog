"""在后台检测本地 HTTP 代理，失败时重试直连。"""

from __future__ import annotations

import os
import socket
import threading
import time

PROXY_HOST = "127.0.0.1"
PROXY_PORTS = (7890, 7897, 10809)
CONNECT_TIMEOUT = 0.08
NO_PROXY = "localhost,127.0.0.1,::1"
POLL_SECONDS = 3.0

_lock = threading.Lock()
_state: dict[str, object] = {
    "url": None,
    "thread": None,
}


def _user_proxy_configured() -> bool:
    return bool(
        os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    )


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(
            (PROXY_HOST, port), timeout=CONNECT_TIMEOUT
        ):
            return True
    except OSError:
        return False


def _detect() -> str | None:
    for port in PROXY_PORTS:
        if _port_open(port):
            return f"http://{PROXY_HOST}:{port}"
    return None


def _poll() -> None:
    while True:
        if not _user_proxy_configured():
            url = _detect()
            with _lock:
                _state["url"] = url
        time.sleep(POLL_SECONDS)


def configure_proxy() -> str | None:
    """启动后台检测器；返回初始代理 URL。"""
    if _user_proxy_configured():
        return None
    with _lock:
        if _state["thread"] is not None:
            return _state["url"]  # type: ignore[return-value]
    url = _detect()
    with _lock:
        _state["url"] = url
        thread = threading.Thread(
            target=_poll,
            name="anilog-proxy",
            daemon=True,
        )
        _state["thread"] = thread
    thread.start()
    return url


def current_proxies() -> dict[str, str] | None:
    if _user_proxy_configured():
        return None
    with _lock:
        started = _state["thread"] is not None
    if not started:
        configure_proxy()
    with _lock:
        url = _state["url"]
    if not url:
        return None
    return {"http": str(url), "https": str(url)}


def mark_proxy_dead() -> None:
    with _lock:
        _state["url"] = None


def http_get(url: str, **kwargs):
    import requests

    proxies = current_proxies()
    try:
        return requests.get(url, proxies=proxies, **kwargs)
    except requests.exceptions.ProxyError:
        mark_proxy_dead()
        return requests.get(
            url,
            proxies={"http": None, "https": None},
            **kwargs,
        )
