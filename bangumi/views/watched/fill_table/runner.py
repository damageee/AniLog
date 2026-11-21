"""自动填表主循环。"""

from __future__ import annotations

import asyncio
import time

import flet as ft

from bangumi.views.watched.fill_table.info import fetch_subject_info
from bangumi.services.bgm_pic import save_subject_image
from bangumi.services.bgm_search import NAME_IDS, search_bgm, _expand_abbreviation
from bangumi.ui.tag_colors import sync_tag_colors
from bangumi.ui.theme import ui_text
from bangumi.ui.feedback import close_dialog
from bangumi.data.watched_data import save_records
from bangumi.data.preferences import Preferences
from bangumi.views.watched.fill_table.constants import FILL_FIELDS
from bangumi.views.watched.fill_table.fields import (
    field_text,
    fields_complete,
    has_cover,
    info_text,
    info_value,
    needs_fill,
    text,
)
from bangumi.views.watched.fill_table.apply import apply_info_field
from bangumi.views.watched.fill_table.log import append_log, log_failure, reset_log
from bangumi.views.watched.fill_table.progress import ticker
from bangumi.views.watched.fill_table.result import (
    _SUMMARY_STATE,
    _show_result,
)
from bangumi.views.watched.fill_table.manual import _show_manual_dialog


def _start_fill(
    owner: "WatchedPage",
    *,
    with_covers: bool,
    covers_only: bool = False,
    ignore_skip: bool = False,
    power: str,
    rename: bool,
    force: bool,
    mark_done: bool,
) -> None:
    if owner._fill_running:
        return
    reset_log()
    _SUMMARY_STATE["done"] = False
    page = owner.page
    total = sum(
        1 for record in owner.records
        if needs_fill(
            record,
            with_covers,
            force,
            covers_only,
            ignore_skip,
        )
    )
    if total == 0:
        notice = ft.AlertDialog(
            modal=True,
            title=ui_text("从 Bangumi 填充表格"),
            content=ui_text("没什么需要导入的呢"),
            actions=[],
        )
        notice.actions = [
            ft.Button(
                content=ui_text("关闭"),
                on_click=lambda event: close_dialog(notice),
            )
        ]
        page.show_dialog(notice)
        return

    owner.pending_manual = []
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
        "cho": 0,
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

    def show_result() -> None:
        if state["shown"]:
            return
        state["shown"] = True
        elapsed = int(
            round(time.monotonic() - float(state["start"]))
        )
        close_dialog(dialog)
        aborted = owner._fill_abort
        _show_result(
            owner,
            elapsed=elapsed,
            ok=int(state["ok"]),
            fail=int(state["fail"]),
            failures=list(state["failures"]),
            cho=int(state["cho"]),
            aborted=aborted,
            status_text="中止" if aborted else "正常结束",
            manual=int(state["cho"]),
            name_pairs=list(state.get("name_pairs", [])),
        )

    def abort(event: ft.ControlEvent) -> None:
        owner._fill_abort = True
        show_result()

    dialog.actions = [
        ft.Button(content=ui_text("中止"), on_click=abort)
    ]
    page.show_dialog(dialog)

    async def worker() -> None:
        try:
            await _run_fill(
                owner,
                with_covers=with_covers,
                covers_only=covers_only,
                ignore_skip=ignore_skip,
                power=power,
                rename=rename,
                force=force,
                mark_done=mark_done,
                state=state,
                status=status,
                progress=progress,
                cho_label=cho_label,
                fail_label=fail_label,
            )
        finally:
            state["elapsed"] = int(
                round(time.monotonic() - float(state["start"]))
            )
            owner._fill_running = False
            if owner._fill_abort:
                return
            if owner.pending_manual:
                state["shown"] = True
                close_dialog(dialog)
                _show_manual_dialog(
                    owner,
                    with_covers=with_covers,
                    covers_only=covers_only,
                    rename=rename,
                    force=force,
                    mark_done=mark_done,
                    first_state=state,
                )
            else:
                show_result()

    page.run_task(worker)
    page.run_task(ticker, owner, state, elapsed_label)


async def _run_fill(
    owner: "WatchedPage",
    *,
    with_covers: bool,
    covers_only: bool = False,
    ignore_skip: bool = False,
    power: str,
    rename: bool,
    force: bool,
    mark_done: bool,
    state: dict[str, object],
    status: ft.Text,
    progress: ft.ProgressBar,
    cho_label: ft.Text,
    fail_label: ft.Text,
) -> None:
    page = owner.page
    # 每次开始填充时重新读取，避免使用页面创建时的旧配置。
    preferences = Preferences.load()
    fixed = set(preferences.fixed_columns)
    records = owner.records
    total = sum(
        1 for record in records
        if needs_fill(
            record,
            with_covers,
            force,
            covers_only,
            ignore_skip,
        )
    )

    def refresh_progress(anime: str) -> None:
        done = int(state["done"])
        # 清空 value 让 spans 生效。
        status.value = None
        status.spans = [
            ft.TextSpan("正在导入"),
            ft.TextSpan(
                str(anime),
                style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            ),
            ft.TextSpan(f"...    {done}/{total}"),
        ]
        progress.value = done / total if total else 0
        cho_label.value = f"{int(state['cho'])}待手动选择"
        fail_label.value = f"{int(state['fail'])}导入失败"
        try:
            # status 使用 spans 渲染，必须一起下发，否则进度文字不刷新。
            page.update(status, progress, cho_label, fail_label)
        except Exception:
            try:
                page.update()
            except Exception:
                pass

    for index, record in enumerate(records):
        if owner._fill_abort:
            return
        if not needs_fill(
            record,
            with_covers,
            force,
            covers_only,
            ignore_skip,
        ):
            continue
        anime = text(record.get("anime"))
        search_text = ""
        search_name_cn = ""
        search_score = 0.0
        filled_fields: list[str] = []
        cover_state = "未取"
        refresh_progress(anime)

        bgm_id = record.get("bgm_id")
        searched = not isinstance(bgm_id, int) or bgm_id == -1
        if searched:
            matched_name = None
            if anime in NAME_IDS:
                matched_name = anime
            else:
                expanded = _expand_abbreviation(anime)
                if expanded in NAME_IDS:
                    matched_name = expanded
            if matched_name is not None:
                bgm_id = NAME_IDS[matched_name]
                record["bgm_id"] = bgm_id
                search_name_cn = matched_name
                search_score = 1.0
                if rename and not covers_only and "anime" not in fixed:
                    old_anime = str(record.get("anime") or "")
                    record["former_name"] = old_anime
                    record["anime"] = matched_name
            else:
                results = await asyncio.to_thread(search_bgm, anime)
                if owner._fill_abort:
                    return
                if not results:
                    state["fail"] = int(state["fail"]) + 1
                    state["done"] = int(state["done"]) + 1
                    state["failures"].append(
                        log_failure(
                            anime,
                            "bgm_search",
                            "搜索无结果",
                        )
                    )
                    refresh_progress(anime)
                    continue
                first = results[0]
                search_score = float(first.get("score") or 0.0)
                manual = False
                if power == "precise":
                    manual = first.get("confidence") != "exact"
                elif power == "confident":
                    manual = first.get("confidence") == "fallback"
                elif power == "fairly":
                    manual = float(first.get("score") or 0) < 0.70
                elif power == "loose":
                    manual = float(first.get("score") or 0) < 0.50
                else:
                    manual = False
                if manual:
                    owner.pending_manual.append((index, anime, results))
                    state["cho"] = int(state["cho"]) + 1
                    state["ok"] = int(state["ok"]) + 1
                    state["done"] = int(state["done"]) + 1
                    refresh_progress(anime)
                    continue
                bgm_id = int(first["id"])
                record["bgm_id"] = bgm_id
                if rename and not covers_only and "anime" not in fixed:
                    chosen_name = str(
                        first.get("name_cn")
                        or first.get("name")
                        or ""
                    ).strip()
                    if chosen_name:
                        old_anime = str(record.get("anime") or "")
                        record["former_name"] = old_anime
                        record["anime"] = chosen_name
                imported_name = text(record.get("anime"))
                search_name_cn = str(
                    first.get("name_cn")
                    or first.get("name")
                    or ""
                ).strip()
                search_text = (
                    f"[搜索：{anime}/{search_name_cn} "
                    f"{float(first.get('score') or 0) * 100:.1f}%]"
                )

        if covers_only:
            if not force and has_cover(record):
                state["done"] = int(state["done"]) + 1
                refresh_progress(anime)
                continue
            path = await asyncio.to_thread(
                save_subject_image,
                bgm_id,
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
                        bgm_id=bgm_id,
                        name_cn=search_name_cn,
                    )
                )
                refresh_progress(anime)
                continue
            cover_state = "已保存"
        else:
            if force or not fields_complete(record):
                info: dict[str, object] = {}
                try:
                    info = await asyncio.to_thread(
                        fetch_subject_info,
                        anime,
                        bgm_id,
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
                            bgm_id=bgm_id,
                            name_cn=search_name_cn
                            or info.get("name_cn"),
                        )
                    )
                    refresh_progress(anime)
                    continue
                if not searched:
                    info_name_cn = str(
                        info.get("name_cn") or ""
                    ).strip()
                    if info_name_cn:
                        search_name_cn = info_name_cn
                if rename and force and not searched and "anime" not in fixed:
                    info_name = str(info.get("name_cn") or "").strip()
                    if info_name:
                        old_anime = str(record.get("anime") or "")
                        record["former_name"] = old_anime
                        record["anime"] = info_name
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
                    bgm_id,
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
                            bgm_id=bgm_id,
                            name_cn=search_name_cn,
                        )
                    )
                    refresh_progress(anime)
                    continue
                cover_state = "已保存"
            elif with_covers:
                cover_state = "已存在"

        imported_name = text(record.get("anime"))
        state["ok"] = int(state["ok"]) + 1
        if mark_done:
            record["skip_fill"] = True
        save_records(owner.records)
        sync_tag_colors(owner.records, owner.preferences)
        state["done"] = int(state["done"]) + 1
        if search_name_cn:
            state["name_pairs"].append(
                (anime, search_name_cn, int(bgm_id), search_score)
            )
        if covers_only:
            name_part = (
                f" name_cn={search_name_cn}"
                if search_name_cn
                else ""
            )
            append_log(
                f"[成功] 原文：{anime} -> 仅封面 "
                f"bgm_id={bgm_id}{name_part}{search_text}"
            )
        else:
            fields_text = (
                "、".join(filled_fields) if filled_fields else "无"
            )
            log_name = search_name_cn or imported_name
            append_log(
                f"[成功] 原文：{anime} -> 导入名：{log_name} "
                f"bgm_id={bgm_id} 字段：{fields_text} "
                f"封面：{cover_state}{search_text}"
            )
        refresh_progress(anime)


