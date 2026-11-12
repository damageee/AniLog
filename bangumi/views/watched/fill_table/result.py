"""导入结果。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.ui.theme import ui_text
from bangumi.ui.feedback import close_dialog
from bangumi.views.watched.fill_table.log import append_log


_SUMMARY_STATE: dict[str, bool] = {"done": False}


def _show_result(
    owner: "WatchedPage",
    *,
    elapsed: int,
    ok: int,
    fail: int,
    failures: list[object],
    cho: int,
    aborted: bool = False,
    status_text: str = "正常结束",
    manual: int = 0,
    name_pairs: list | None = None,
) -> None:
    page = owner.page
    if not _SUMMARY_STATE["done"]:
        _SUMMARY_STATE["done"] = True
        append_log("=== 导入总结 ===")
        append_log(
            f"成功 {ok} 条，手动 {manual} 条，失败 {fail} 条；"
            f"{status_text}"
        )
        append_log("失败条目：")
        if failures:
            for name in failures:
                append_log(f"- {name}")
        else:
            append_log("- （无）")
        append_log("=== 名称差异 ===")
        pairs = name_pairs or []
        diffs = []
        for pair in pairs:
            if len(pair) >= 4:
                old, new, sid, score = pair
            else:
                old, new, sid = pair
                score = 0.0
            if (
                str(new).strip()
                and str(old).strip() != str(new).strip()
                and score < 1.0 - 1e-9
            ):
                diffs.append((old, new, sid))
        if diffs:
            for old, new, sid in diffs:
                append_log(f"- {old} -> {new} (bgm_id={sid})")
        else:
            append_log("- （无）")

    controls: list[ft.Control] = [
        ui_text(
            f"{elapsed}s成功导入{ok}条，{fail}条导入失败",
            size=13,
        )
    ]
    controls.extend(ui_text(str(name), size=13) for name in failures)
    if cho > 0:
        controls.append(
            ui_text(f"另有 {cho} 条待手动选择", size=13)
        )
    controls.append(ui_text("详细日志可在设置查看", size=12))

    height = min(420, max(80, 40 + 22 * len(controls)))
    title = "导出中止" if aborted else "导入完成"
    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text(title),
        content=ft.Container(
            width=520,
            height=height,
            content=ft.Column(
                tight=True,
                spacing=4,
                scroll=ft.ScrollMode.AUTO,
                controls=controls,
            ),
        ),
        actions=[],
    )

    def close(event: ft.ControlEvent) -> None:
        close_dialog(dialog)
        sync_tag_colors(owner.records, owner.preferences)
        owner.refresh()

    dialog.actions = [
        ft.Button(content=ui_text("关闭"), on_click=close)
    ]
    page.show_dialog(dialog)


