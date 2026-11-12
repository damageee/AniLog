"""设置页的应用数据导入。"""

from __future__ import annotations

import json
from pathlib import (
    Path,
)
import flet as ft
import bangumi.io.app_data as app_data
from bangumi.io.app_data import (
    collect_storage_files,
)
from bangumi.ui.feedback import (
    confirmation_dialog,
    show_error_dialog,
)
from bangumi.views.widgets.toast import (
    show_toast,
)
from bangumi.views.widgets.file_picker import (
    ensure_file_picker,
)


collect_export_files = collect_storage_files


validate_export_document = app_data.validate_export_document


apply_import_files = app_data.apply_import_files


async def import_app_data(page: ft.Page) -> None:
    picker = ensure_file_picker(page)
    try:
        results = await picker.pick_files(
            dialog_title="导入应用数据",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            allow_multiple=False,
            with_data=True,
        )
    except Exception as error:
        show_error_dialog(
            page,
            title="导入失败",
            message=str(error),
        )
        return
    if not results:
        return

    # 选择器只选中导出产生的单个汇总 JSON。
    selected = results[0]
    try:
        raw = getattr(selected, "bytes", None)
        if raw:
            text = raw.decode("utf-8")
        else:
            path = getattr(selected, "path", None)
            if not path:
                raise ValueError("无法读取所选文件")
            text = Path(str(path)).read_text(encoding="utf-8")
        document = json.loads(text)
    except Exception as error:
        show_error_dialog(
            page,
            title="导入失败",
            message=str(error),
        )
        return

    try:
        app_data.apply_export_document(document)
    except Exception as error:
        show_error_dialog(
            page,
            title="导入失败",
            message=str(error),
        )
        return

    app_data.reload_app(page)
    show_toast(page, "导入成功")


def start_import(page: ft.Page) -> None:
    def confirm(event: ft.ControlEvent) -> None:
        page.pop_dialog()
        page.run_task(import_app_data, page)

    page.show_dialog(
        confirmation_dialog(
            page,
            title="导入应用数据",
            message=(
                "导入后可能会覆盖原有应用配置和用户数据，"
                "你要继续吗？"
            ),
            confirm_label="继续",
            on_confirm=confirm,
        )
    )


