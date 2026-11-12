"""FilePicker 服务的复用辅助。"""

from __future__ import annotations

import flet as ft


def ensure_file_picker(page: ft.Page) -> ft.FilePicker:
    for service in page.services:
        if isinstance(service, ft.FilePicker):
            return service
    picker = ft.FilePicker()
    page.services.append(picker)
    return picker
