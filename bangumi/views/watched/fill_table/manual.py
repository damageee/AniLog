"""手动选择与第二遍导入。"""

from __future__ import annotations

import asyncio
import time

import flet as ft

from bangumi.views.watched.fill_table.info import fetch_subject_info
from bangumi.services.bgm_pic import save_subject_image
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.ui.theme import ui_text
from bangumi.ui.feedback import close_dialog
from bangumi.ui.interaction import (
    hover_icon,
)
from bangumi.data.watched_data import save_records
from bangumi.data.preferences import Preferences
from bangumi.views.watched.fill_table.constants import FILL_FIELDS
from bangumi.views.watched.fill_table.fields import (
    field_text,
    has_cover,
    info_text,
    info_value,
    text,
)
from bangumi.views.watched.fill_table.apply import apply_info_field
from bangumi.views.watched.fill_table.log import append_log, log_failure
from bangumi.views.watched.fill_table.progress import ticker
from bangumi.views.watched.fill_table.result import _show_result


def _show_manual_dialog(
    owner: "WatchedPage",
    *,
    with_covers: bool,
    covers_only: bool = False,
    rename: bool,
    force: bool,
    mark_done: bool,
    first_state: dict[str, object],
) -> None:
    page = owner.page
    entries = list(owner.pending_manual)
    selections: dict[int, int] = {}

    def first_id(results: list[dict]) -> int | None:
        for item in results:
            subject_id = item.get("id")
            if isinstance(subject_id, int):
                return subject_id
        return None

    for index, _, results in entries:
        subject_id = first_id(results)
        if subject_id is not None:
            selections[index] = subject_id

    current = {"pos": 0}
    dropdown = ft.Dropdown(width=320, options=[], value=None)
    anime_label = ui_text("", size=13)
    position_label = ui_text("", size=13)
    left_button = hover_icon(
        page,
        ft.Icons.CHEVRON_LEFT,
        on_click=None,
        tooltip=None,
    )
    right_button = hover_icon(
        page,
        ft.Icons.CHEVRON_RIGHT,
        on_click=None,
        tooltip=None,
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("手动选择"),
        content=ft.Column(
            tight=True,
            spacing=10,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[left_button, dropdown, right_button],
                ),
                anime_label,
                position_label,
            ],
        ),
        actions=[],
    )

    def load(pos: int, *, save_current: bool = False) -> None:
        if save_current:
            index = entries[current["pos"]][0]
            value = dropdown.value
            if value is not None:
                try:
                    selections[index] = int(value)
                except (TypeError, ValueError):
                    pass
        current["pos"] = pos
        index, anime, results = entries[pos]
        options: list[ft.DropdownOption] = [
            ft.DropdownOption(key="-1", text="不导入")
        ]
        for item in results:
            subject_id = item.get("id")
            if not isinstance(subject_id, int):
                continue
            label = str(
                item.get("name_cn") or item.get("name") or ""
            ).strip()
            if not label:
                continue
            options.append(
                ft.DropdownOption(key=str(subject_id), text=label)
            )
        dropdown.options = options
        selected = selections.get(index)
        if selected is None:
            for option in options:
                if option.key != "-1":
                    selected = int(option.key)
                    break
            if selected is not None:
                selections[index] = selected
        dropdown.value = (
            str(selected) if selected is not None else None
        )
        anime_label.value = f"原文：{anime}"
        position_label.value = f"{pos + 1}/{len(entries)}"
        left_button.disabled = pos <= 0
        right_button.disabled = pos >= len(entries) - 1
        try:
            dialog.update()
        except Exception:
            pass

    def go(delta: int) -> None:
        target = current["pos"] + delta
        if 0 <= target < len(entries):
            load(target, save_current=True)

    def confirm(event: ft.ControlEvent) -> None:
        index = entries[current["pos"]][0]
        value = dropdown.value
        if value is not None:
            try:
                selections[index] = int(value)
            except (TypeError, ValueError):
                pass
        close_dialog(dialog)
        _start_second_pass(
            owner,
            with_covers=with_covers,
            covers_only=covers_only,
            rename=rename,
            force=force,
            mark_done=mark_done,
            first_state=first_state,
            selections=selections,
        )

    def cancel(event: ft.ControlEvent) -> None:
        close_dialog(dialog)
        _show_result(
            owner,
            elapsed=int(first_state.get("elapsed") or 0),
            ok=int(first_state["ok"]),
            fail=int(first_state["fail"]),
            failures=list(first_state["failures"]),
            cho=int(first_state["cho"]),
            aborted=False,
            status_text="手动选择取消",
            manual=int(first_state["cho"]),
            name_pairs=list(first_state.get("name_pairs", [])),
        )

    left_button.on_click = lambda event: go(-1)
    right_button.on_click = lambda event: go(1)
    dialog.actions = [
        ft.TextButton(content=ui_text("取消"), on_click=cancel),
        ft.Button(content=ui_text("确认"), on_click=confirm),
    ]
    load(0)
    page.show_dialog(dialog)


def _start_second_pass(
    owner: "WatchedPage",
    *,
    with_covers: bool,
    covers_only: bool = False,
    rename: bool,
    force: bool,
    mark_done: bool,
    first_state: dict[str, object],
    selections: dict[int, int],
) -> None:
    page = owner.page
    owner._fill_abort = False
    owner._fill_running = True

    status = ui_text("准备中…", size=13)
    progress = ft.ProgressBar(value=0, height=12)
    cho_label = ui_text("0待手动选择", size=13)
    fail_label = ui_text("0导入失败", size=13)
    elapsed_label = ui_text("0s", size=13)

    state: dict[str, object] = {
        "ok": 0,
        "fail": 0,
        "done": 0,
        "failures": [],
        "name_pairs": [],
        "start": time.monotonic(),
        "shown": False,
    }

    dialog = ft.AlertDialog(
        modal=True,
        title=ui_text("正在导入"),
        content=ft.Column(
            tight=True,
            spacing=10,
            controls=[
                status,
                progress,
                cho_label,
                fail_label,
                elapsed_label,
            ],
        ),
        actions=[],
    )

    def show_combined() -> None:
        if state["shown"]:
            return
        state["shown"] = True
        second_elapsed = int(
            round(time.monotonic() - float(state["start"]))
        )
        first_elapsed = int(first_state.get("elapsed") or 0)
        first_ok = int(first_state["ok"])
        first_cho = int(first_state["cho"])
        first_fail = int(first_state["fail"])
        ok = max(0, first_ok - first_cho) + int(state["ok"])
        fail = first_fail + int(state["fail"])
        failures = (
            list(first_state["failures"])
            + list(state["failures"])
        )
        close_dialog(dialog)
        name_pairs = (
            list(first_state.get("name_pairs", []))
            + list(state.get("name_pairs", []))
        )
        aborted = owner._fill_abort
        _show_result(
            owner,
            elapsed=first_elapsed + second_elapsed,
            ok=ok,
            fail=fail,
            failures=failures,
            cho=0,
            aborted=aborted,
            status_text="中止" if aborted else "正常结束",
            manual=first_cho,
            name_pairs=name_pairs,
        )

    def abort(event: ft.ControlEvent) -> None:
        owner._fill_abort = True
        show_combined()

    dialog.actions = [
        ft.Button(content=ui_text("中止"), on_click=abort)
    ]
    page.show_dialog(dialog)

    async def worker() -> None:
        try:
            await _run_manual_fill(
                owner,
                with_covers=with_covers,
                covers_only=covers_only,
                rename=rename,
                force=force,
                mark_done=mark_done,
                selections=selections,
                state=state,
                status=status,
                progress=progress,
                fail_label=fail_label,
            )
        finally:
            owner._fill_running = False
            if not owner._fill_abort:
                show_combined()

    page.run_task(worker)
    page.run_task(ticker, owner, state, elapsed_label)


async def _run_manual_fill(
    owner: "WatchedPage",
    *,
    with_covers: bool,
    covers_only: bool = False,
    rename: bool,
    force: bool,
    mark_done: bool,
    selections: dict[int, int],
    state: dict[str, object],
    status: ft.Text,
    progress: ft.ProgressBar,
    fail_label: ft.Text,
) -> None:
    page = owner.page
    # 每次开始填充时重新读取，避免使用页面创建时的旧配置。
    preferences = Preferences.load()
    fixed = set(preferences.fixed_columns)
    entries = list(owner.pending_manual)
    total = len(entries)

    def refresh_progress(anime: str) -> None:
        done = int(state["done"])
        status.value = ""
        status.spans = [
            ft.TextSpan("正在导入"),
            ft.TextSpan(
                str(anime),
                style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            ),
            ft.TextSpan(f"...    {done}/{total}"),
        ]
        progress.value = done / total if total else 0
        fail_label.value = f"{int(state['fail'])}导入失败"
        try:
            page.update(progress, fail_label)
        except Exception:
            page.update()

    for index, anime, results in entries:
        if owner._fill_abort:
            return
        search_text = ""
        filled_fields: list[str] = []
        cover_state = "未取"
        record = owner.records[index]
        subject_id = selections.get(index)
        if subject_id is None:
            for item in results:
                candidate = item.get("id")
                if isinstance(candidate, int):
                    subject_id = candidate
                    break
        if subject_id is None:
            state["fail"] = int(state["fail"]) + 1
            state["done"] = int(state["done"]) + 1
            state["failures"].append(
                log_failure(
                    anime,
                    "bgm_search",
                    "没有可用结果",
                )
            )
            refresh_progress(anime)
            continue
        if subject_id == -1:
            state["done"] = int(state["done"]) + 1
            append_log(
                f"【手动选择】原文：{anime} -> 不导入"
            )
            refresh_progress(anime)
            continue
        record["bgm_id"] = subject_id
        selected_name = ""
        selected_score = 0.0
        for item in results:
            if item.get("id") == subject_id:
                selected_name = str(
                    item.get("name_cn")
                    or item.get("name")
                    or ""
                ).strip()
                selected_score = float(item.get("score") or 0.0)
                break
        if rename and not covers_only and "anime" not in fixed:
            if selected_name:
                old_anime = str(record.get("anime") or "")
                record["former_name"] = old_anime
                record["anime"] = selected_name
        imported_name = text(record.get("anime"))
        search_name_cn = selected_name
        first = results[0] if results else {}
        search_text = (
            f"[搜索：{anime}/{search_name_cn} "
            f"{float(first.get('score') or 0) * 100:.1f}%]"
        )
        refresh_progress(anime)

        if covers_only:
            if not force and has_cover(record):
                state["done"] = int(state["done"]) + 1
                refresh_progress(anime)
                continue
            path = await asyncio.to_thread(
                save_subject_image,
                subject_id,
            )
            if owner._fill_abort:
                return
            if path is None:
                state["fail"] = int(state["fail"]) + 1
                state["done"] = int(state["done"]) + 1
                state["failures"].append(
                    log_failure(
                        anime,
                        "bgm_pic",
                        "封面获取失败",
                        bgm_id=subject_id,
                        name_cn=search_name_cn,
                    )
                )
                refresh_progress(anime)
                continue
            cover_state = "已保存"
        else:
            info: dict[str, object] = {}
            try:
                info = await asyncio.to_thread(
                    fetch_subject_info,
                    anime,
                    subject_id,
                    record,
                    fixed,
                    force,
                )
            except Exception:
                info = {}
            if owner._fill_abort:
                return
            returned = {
                field: info_text(
                    field,
                    info_value(info, field, key),
                )
                for field, key in FILL_FIELDS
            }
            if info and not any(returned.values()):
                state["fail"] = int(state["fail"]) + 1
                state["done"] = int(state["done"]) + 1
                reason = (
                    str(info.get("error") or "").strip()
                    or "详情为空"
                )
                state["failures"].append(
                    log_failure(
                        anime,
                        "bgm_info",
                        reason,
                        bgm_id=subject_id,
                        name_cn=search_name_cn,
                    )
                )
                refresh_progress(anime)
                continue
            if force:
                for field, key in FILL_FIELDS:
                    if field in fixed:
                        continue
                    apply_info_field(record, field, info, key)
                    if returned[field]:
                        filled_fields.append(key)
            else:
                for field, key in FILL_FIELDS:
                    if field in fixed:
                        continue
                    if field_text(record, field):
                        continue
                    value = returned[field]
                    if value:
                        apply_info_field(record, field, info, key)
                        filled_fields.append(key)

            if with_covers and (force or not has_cover(record)):
                path = await asyncio.to_thread(
                    save_subject_image,
                    subject_id,
                )
                if owner._fill_abort:
                    return
                if path is None:
                    state["fail"] = int(state["fail"]) + 1
                    state["done"] = int(state["done"]) + 1
                    state["failures"].append(
                        log_failure(
                            anime,
                            "bgm_pic",
                            "封面获取失败",
                            bgm_id=subject_id,
                            name_cn=search_name_cn,
                        )
                    )
                    refresh_progress(anime)
                    continue
                cover_state = "已保存"
            elif with_covers:
                cover_state = "已存在"

        state["ok"] = int(state["ok"]) + 1
        if mark_done:
            record["skip_fill"] = True
        save_records(owner.records)
        sync_tag_colors(owner.records, owner.preferences)
        state["done"] = int(state["done"]) + 1
        if search_name_cn:
            state["name_pairs"].append(
                (anime, search_name_cn, int(subject_id), selected_score)
            )
        append_log(
            f"【手动选择】原文：{anime} -> 选择：{selected_name} "
            f"bgm_id={subject_id}{search_text}"
        )
        refresh_progress(anime)


