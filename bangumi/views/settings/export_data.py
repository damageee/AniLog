"""设置页的应用数据导出。"""

from __future__ import annotations

from pathlib import (
    Path,
)
import flet as ft
from bangumi.io.app_data import (
    build_export_document,
    collect_storage_files,
    export_document_bytes,
)
from bangumi.ui.feedback import (
    show_error_dialog,
)
from bangumi.views.widgets.toast import (
    show_toast,
)
from bangumi.views.widgets.file_picker import (
    ensure_file_picker,
)


EXPORT_FILE_NAME = "Anilog_config.json"


async def export_app_data(page: ft.Page) -> None:
    files = collect_storage_files()
    if not files:
        show_toast(page, "没有可导出的 JSON 文件")
        return

    document = build_export_document(files)
    data = export_document_bytes(document)
    picker = ensure_file_picker(page)
    try:
        path = await picker.save_file(
            dialog_title="导出应用数据",
            file_name=EXPORT_FILE_NAME,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            src_bytes=data,
        )
    except Exception as error:
        show_error_dialog(
            page,
            title="导出失败",
            message=str(error),
        )
        return

    if not path:
        return

    target = Path(str(path))
    if not target.suffix:
        target = Path(str(target) + ".json")
        source = Path(str(path))
        try:
            if source.exists():
                source.replace(target)
        except OSError as error:
            show_error_dialog(
                page,
                title="导出失败",
                message=str(error),
            )
            return
    show_toast(page, f"已导出：{target.name}")


