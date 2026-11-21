"""将图片文件以位图形式复制到 Windows 剪贴板。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import time
from io import BytesIO

from PIL import Image

CF_DIB = 8
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
GMEM_FLAGS = GMEM_MOVEABLE | GMEM_ZEROINIT


def _load_functions():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    w = ctypes.wintypes
    user32.OpenClipboard.argtypes = [w.HWND]
    user32.OpenClipboard.restype = w.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = w.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = w.BOOL
    user32.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
    user32.SetClipboardData.restype = w.HANDLE
    kernel32.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = w.HGLOBAL
    kernel32.GlobalLock.argtypes = [w.HGLOBAL]
    kernel32.GlobalLock.restype = w.LPVOID
    kernel32.GlobalUnlock.argtypes = [w.HGLOBAL]
    kernel32.GlobalUnlock.restype = w.BOOL
    kernel32.GlobalFree.argtypes = [w.HGLOBAL]
    kernel32.GlobalFree.restype = w.HGLOBAL
    return user32, kernel32


def copy_image_bytes(data: bytes) -> bool:
    """将图片字节放入剪贴板；失败返回 False。"""
    if os.name != "nt":
        return False
    try:
        with Image.open(BytesIO(data)) as image:
            rgb = image.convert("RGB")
            buffer = BytesIO()
            rgb.save(buffer, format="BMP")
        dib = buffer.getvalue()[14:]
        return _set_clipboard_dib(dib)
    except Exception:
        return False


def _set_clipboard_dib(dib: bytes) -> bool:
    user32, kernel32 = _load_functions()
    handle = None
    opened = False
    try:
        for _ in range(10):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)
        if not opened:
            return False
        try:
            user32.EmptyClipboard()

            handle = kernel32.GlobalAlloc(GMEM_FLAGS, len(dib))
            if not handle:
                return False

            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return False
            try:
                ctypes.memmove(pointer, dib, len(dib))
            finally:
                kernel32.GlobalUnlock(handle)

            if not user32.SetClipboardData(CF_DIB, handle):
                return False
            # 所有权已转移给剪贴板。
            handle = None
            return True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False
    finally:
        if handle:
            try:
                kernel32.GlobalFree(handle)
            except Exception:
                pass
