"""设置页的设备同步对话框。"""

from __future__ import annotations

import asyncio
import threading

import flet as ft
import bangumi.io.app_data as app_data
from bangumi.ui.theme import (
    ui_text,
)
from bangumi.ui.feedback import (
    show_error_dialog,
)
from bangumi.views.widgets.toast import (
    show_toast,
)
from bangumi.ui.feedback import (
    close_dialog,
)


_ACTIVE_SYNC_DIALOGS: dict[int, ft.AlertDialog] = {}


def open_sync_dialog(page: ft.Page) -> None:
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ui_text("数据同步"),
            content=ui_text("选择本机在此次同步中的角色："),
            actions=[
                ft.TextButton(
                    content=ui_text("共享本机数据"),
                    on_click=lambda event: _choose_share(page),
                ),
                ft.TextButton(
                    content=ui_text("从其他设备拉取"),
                    on_click=lambda event: _choose_pull(page),
                ),
                ft.TextButton(
                    content=ui_text("取消"),
                    on_click=lambda event: page.pop_dialog(),
                ),
            ],
        )
    )


def _choose_share(page: ft.Page) -> None:
    page.pop_dialog()
    server = app_data.ShareServer()
    try:
        server.start()
    except (app_data.SyncError, OSError) as error:
        show_error_dialog(
            page,
            title="共享失败",
            message=str(error),
        )
        return

    addresses = app_data.local_ip_addresses()
    lines: list[ft.Control] = [
        ui_text(f"设备名：{server.name}", size=12),
    ]
    if addresses:
        lines.extend(
            ui_text(f"{address}:{server.port}", size=12)
            for address in addresses
        )
    else:
        lines.append(
            ui_text(
                "未检测到局域网地址，请检查网络或防火墙设置。",
                size=12,
            )
        )
    lines.extend(
        [
            ui_text(
                f"配对码：{server.code}",
                size=20,
                weight=ft.FontWeight.BOLD,
            ),
            ui_text(
                "配对码 5 分钟内有效，成功拉取一次后自动停止。",
                size=12,
            ),
            ui_text(
                "Windows 首次监听时请允许专用网络访问。",
                size=12,
            ),
        ]
    )

    progress_bar = ft.ProgressBar(width=340, value=0)
    progress_text = ui_text("等待设备连接…", size=12)
    progress_file = ui_text("", size=11)

    async def _share_progress(sent, total, name) -> None:
        progress_bar.value = 0 if total <= 0 else sent / total
        progress_text.value = f"正在同步 {sent}/{total}"
        progress_file.value = name
        try:
            page.update(progress_bar, progress_text, progress_file)
        except Exception:
            pass

    server.on_progress = lambda sent, total, name: page.run_task(
        _share_progress, sent, total, name
    )

    def abort_share(event: ft.ControlEvent | None = None) -> None:
        server.abort()
        server.stop()
        page.pop_dialog()
        show_toast(page, "已中止传输")

    def stop_share(event: ft.ControlEvent | None = None) -> None:
        server.stop()
        page.pop_dialog()
        show_toast(page, "已停止共享")

    def close_dialog(event: ft.ControlEvent | None = None) -> None:
        server.stop()
        page.pop_dialog()

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("共享本机数据"),
        content=ft.Container(
            width=360,
            content=ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    *lines,
                    progress_bar,
                    progress_text,
                    progress_file,
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                content=ui_text("中止"),
                on_click=abort_share,
            ),
            ft.TextButton(
                content=ui_text("停止共享"),
                on_click=stop_share,
            ),
            ft.TextButton(
                content=ui_text("关闭"),
                on_click=close_dialog,
            ),
        ],
    )
    dialog.on_dismiss = lambda event: server.stop()

    previous_close = page.on_close

    def on_close(event: ft.ControlEvent | None = None) -> None:
        server.stop()
        if previous_close is not None:
            previous_close(event)

    page.on_close = on_close
    page.show_dialog(dialog)
    page.run_task(_watch_share, page, server, dialog)


async def _watch_share(
    page: ft.Page,
    server: app_data.ShareServer,
    dialog: ft.AlertDialog,
) -> None:
    while True:
        if server.served.is_set():
            if dialog.open:
                page.pop_dialog()
            show_toast(page, "数据已发送")
            return
        if not server.is_running():
            return
        if not dialog.open:
            server.stop()
            return
        await asyncio.sleep(0.5)


def _choose_pull(page: ft.Page) -> None:
    page.pop_dialog()

    def start(include_covers: bool) -> None:
        page.pop_dialog()
        show_toast(page, "正在扫描局域网设备…")
        page.run_task(_scan_devices, page, include_covers)

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ui_text("同步封面图"),
            content=ui_text("是否同步缓存的封面图？"),
            actions=[
                ft.TextButton(
                    content=ui_text("否"),
                    on_click=lambda event: start(False),
                ),
                ft.TextButton(
                    content=ui_text("是"),
                    on_click=lambda event: start(True),
                ),
            ],
        )
    )


async def _scan_devices(
    page: ft.Page,
    include_covers: bool,
) -> None:
    devices = await asyncio.to_thread(
        app_data.discover_devices,
        app_data.SCAN_TIMEOUT,
    )
    _show_pull_dialog(page, devices, include_covers)


def _parse_address(text: str) -> tuple[str, int]:
    value = text.strip().replace("：", ":")
    host, separator, port_text = value.rpartition(":")
    if not separator or not host or not port_text.isdigit():
        raise ValueError("地址格式应为 IP:端口")
    port = int(port_text)
    if not 0 < port < 65536:
        raise ValueError("端口超出范围")
    return host, port


def _show_pull_dialog(
    page: ft.Page,
    devices: list[dict[str, object]],
    include_covers: bool,
) -> None:
    device_names = {
        f"{device['host']}:{device['port']}": str(device["name"])
        for device in devices
    }
    options = [
        ft.DropdownOption(
            key=f"{device['host']}:{device['port']}",
            text=(
                f"{device['name']} "
                f"({device['host']}:{device['port']})"
            ),
        )
        for device in devices
    ]
    device_dropdown = ft.Dropdown(
        label="发现的设备",
        width=340,
        options=options,
        hint_text=(
            "未发现设备，请手动输入"
            if not options
            else "选择一台设备"
        ),
    )
    manual_field = ft.TextField(
        label="手动 IP:端口（兼容中文冒号）",
        hint_text="192.168.1.10:47824",
    )
    pair_field = ft.TextField(
        label="配对码",
        hint_text="6 位数字",
        max_length=6,
    )
    status = ui_text(
        "未发现设备，可手动输入 IP:端口" if not options else "",
        size=12,
    )
    pull_button = ft.Button(content=ui_text("拉取"))
    progress_bar = ft.ProgressBar(width=340, value=0, visible=False)
    progress_text = ui_text("", size=12, visible=False)
    progress_file = ui_text("", size=11, visible=False)
    abort_event = threading.Event()
    progress_state = {"received": 0, "total": 0}

    async def _pull_progress(received: int, total: int, name: str) -> None:
        progress_state["received"] = received
        progress_state["total"] = total
        progress_bar.value = 0 if total <= 0 else received / total
        progress_text.value = f"正在同步 {received}/{total}"
        progress_file.value = name
        try:
            page.update(progress_bar, progress_text, progress_file)
        except Exception:
            pass

    def on_progress(received: int, total: int, name: str) -> None:
        page.run_task(_pull_progress, received, total, name)

    abort_button = ft.TextButton(
        content=ui_text("中止"),
        disabled=True,
    )

    def abort_pull(event: ft.ControlEvent | None = None) -> None:
        abort_event.set()

    abort_button.on_click = abort_pull

    def target() -> tuple[str, int, str]:
        manual = (manual_field.value or "").strip()
        if manual:
            host, port = _parse_address(manual)
            return host, port, manual
        key = str(device_dropdown.value or "").strip()
        if not key:
            raise ValueError("请选择设备或输入 IP:端口")
        host, port = _parse_address(key)
        return host, port, device_names.get(key, key)

    async def do_pull() -> None:
        try:
            host, port, source = target()
        except ValueError as error:
            status.value = str(error)
            status.update()
            return
        code = (pair_field.value or "").strip()
        if not code:
            status.value = "请输入配对码"
            status.update()
            return

        pull_button.disabled = True
        abort_button.disabled = False
        device_dropdown.visible = False
        manual_field.visible = False
        pair_field.visible = False
        status.visible = False
        progress_bar.visible = True
        progress_text.visible = True
        progress_file.visible = True
        try:
            page.update()
        except Exception:
            pass
        try:
            document, aborted = await asyncio.to_thread(
                app_data.pull_document,
                host,
                port,
                code,
                app_data.NETWORK_TIMEOUT,
                include_covers=include_covers,
                progress=on_progress,
                abort_event=abort_event,
            )
        except app_data.SyncError as error:
            close_dialog(dialog)
            show_error_dialog(
                page,
                title="拉取失败",
                message=_sync_error_message(error),
            )
            return
        except Exception as error:
            close_dialog(dialog)
            show_error_dialog(
                page,
                title="拉取失败",
                message=str(error),
            )
            return
        finally:
            if dialog.open:
                pull_button.disabled = False
                abort_button.disabled = True
                pull_button.update()
                abort_button.update()

        close_dialog(dialog)
        _show_sync_summary(
            page,
            document,
            source,
            aborted=aborted,
            received=progress_state["received"],
            total=progress_state["total"],
        )

    pull_button.on_click = lambda event: page.run_task(do_pull)

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("从其他设备拉取"),
        content=ft.Container(
            width=360,
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    device_dropdown,
                    manual_field,
                    pair_field,
                    status,
                    progress_bar,
                    progress_text,
                    progress_file,
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                content=ui_text("取消"),
                on_click=lambda event: close_dialog(dialog),
            ),
            abort_button,
            pull_button,
        ],
    )
    page.show_dialog(dialog)


def _sync_error_message(error: app_data.SyncError) -> str:
    if error.code == "pair":
        return "配对码错误"
    if error.code == "timeout":
        return "连接超时"
    if error.code == "version":
        return "版本不匹配"
    if error.code == "invalid":
        return "数据非法"
    return str(error)


def _show_sync_summary(
    page: ft.Page,
    document: dict[str, object],
    source: str,
    *,
    aborted: bool = False,
    received: int = 0,
    total: int = 0,
) -> None:
    files = document.get("files")
    covers = document.get("covers")
    file_count = len(files) if isinstance(files, dict) else 0
    cover_count = len(covers) if isinstance(covers, dict) else 0
    item_count = file_count + cover_count
    if total > 0:
        item_count = total
    lines = [
        f"来源设备：{source}",
        f"文件数：{item_count}",
        f"其中：JSON {file_count} 个，封面图 {cover_count} 张",
        f"版本：{document.get('version', '')}",
    ]
    if aborted:
        lines.append(
            f"已接收部分数据（尚未应用）：{received}/{total}"
        )
    summary = ui_text("\n".join(lines), size=14)

    previous = _ACTIVE_SYNC_DIALOGS.pop(id(page), None)
    if previous is not None:
        try:
            if previous.open:
                previous.open = False
                previous.update()
        except Exception:
            pass

    dialog: ft.AlertDialog | None = None

    def close_dialog() -> None:
        if _ACTIVE_SYNC_DIALOGS.get(id(page)) is dialog:
            _ACTIVE_SYNC_DIALOGS.pop(id(page), None)
        if dialog is not None and dialog.open:
            dialog.open = False
            dialog.update()

    async def finish_apply() -> None:
        await asyncio.sleep(0.2)
        try:
            app_data.apply_export_document(document)
        except Exception as error:
            show_error_dialog(
                page,
                title="同步失败",
                message=str(error),
            )
            return
        while page.pop_dialog() is not None:
            pass
        app_data.reload_app(page)
        show_toast(page, "同步完成")

    def apply(event: ft.ControlEvent) -> None:
        close_dialog()
        page.run_task(finish_apply)

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("传输已中止" if aborted else "确认同步"),
        content=summary,
        actions=(
            [
                ft.TextButton(
                    content=ui_text("暂不应用"),
                    on_click=lambda event: close_dialog(),
                ),
                ft.Button(
                    content=ui_text("应用已接收数据"),
                    on_click=apply,
                ),
            ]
            if aborted
            else [
                ft.TextButton(
                    content=ui_text("取消"),
                    on_click=lambda event: close_dialog(),
                ),
                ft.Button(
                    content=ui_text("应用"),
                    on_click=apply,
                ),
            ]
        ),
    )
    _ACTIVE_SYNC_DIALOGS[id(page)] = dialog
    page.show_dialog(dialog)


