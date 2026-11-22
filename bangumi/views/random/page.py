"""随机页面：骰子请求、封面下载与瀑布排列。"""

from __future__ import annotations

import asyncio
import base64
import time

import flet as ft
from PIL import Image

from bangumi.core.cover_proc import process_cover_bytes
from bangumi.services.proxy import http_get

from bangumi.ui.interaction import back_icon, hover_icon, hover_zoom
from bangumi.ui.layout import page_padding
from bangumi.ui.theme import ui_text
from bangumi.views.navigation.stack import register_resize_handler
from bangumi.views.random import layout
from bangumi.views.random.detail import open_random_detail
from bangumi.views.random.session import bind, session
from bangumi.views.random.settings import (
    build_random_settings_view,
    open_random_settings,
)
from bangumi.views.random.state import (
    get_state,
    to_query,
)
from bangumi.views.widgets.toast import show_toast

API_URL = "https://api.tenrai.org/random/anime"
COVER_PATH = "assets/pic/cover.jpg"
REQUEST_INTERVAL = 1.7


def _fetch_random(page: ft.Page) -> dict:
    query = to_query(get_state(page))
    response = None
    printed = False
    try:
        response = http_get(API_URL, params=query, timeout=15)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            print(
                f"[random] status=429 retry_after={retry_after}"
                f" body={response.text[:800]}",
                flush=True,
            )
            printed = True
            try:
                wait = float(retry_after or 2)
            except (TypeError, ValueError):
                wait = 2.0
            time.sleep(min(wait, 10.0))
            response = http_get(
                API_URL, params=query, timeout=15
            )
        if response.status_code != 200:
            if not printed:
                print(
                    f"[random] status={response.status_code}"
                    f" body={response.text[:800]}",
                    flush=True,
                )
                printed = True
            response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            print(
                f"[random] json_error"
                f" status={response.status_code}"
                f" body={response.text[:800]}",
                flush=True,
            )
            raise
        data = (
            payload.get("data")
            if isinstance(payload, dict)
            else None
        )
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        if not printed:
            body = (
                getattr(response, "text", "")
                if response is not None
                else ""
            )
            status = (
                getattr(response, "status_code", None)
                if response is not None
                else None
            )
            print(
                f"[random] error={type(exc).__name__}"
                f" info={exc} status={status}"
                f" body={str(body)[:800]}",
                flush=True,
            )
        raise


def _normalize_url(value: str) -> str:
    url = str(value)
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith("http"):
        return "https://" + url
    return url


def _image_bytes(data: dict) -> tuple[str, float]:
    # 兼容外层 {"data": {...}} 结构。
    if isinstance(data.get("data"), dict):
        data = data["data"]
    images = data.get("images") or {}
    if not isinstance(images, dict):
        images = {}
    candidates: list[tuple[str, str]] = []
    for source in ("webp", "jpg"):
        block = images.get(source)
        if not isinstance(block, dict):
            continue
        for field in (
            "image_url",
            "large_image_url",
            "small_image_url",
        ):
            value = block.get(field)
            if value:
                candidates.append(
                    (f"{source}.{field}", _normalize_url(value))
                )
    for field, url in candidates:
        response = None
        try:
            response = http_get(url, timeout=15)
            if response.status_code != 200:
                continue
            raw = response.content
            processed = process_cover_bytes(raw, 480)
            if processed is None:
                continue
            return (
                base64.b64encode(processed).decode("ascii"),
                480 / 679,
            )
        except Exception:
            continue
    try:
        with open(COVER_PATH, "rb") as file:
            fallback = process_cover_bytes(file.read(), 480)
    except OSError:
        fallback = None
    if fallback is not None:
        return base64.b64encode(fallback).decode("ascii"), 480 / 679
    return "", 480 / 679


def _render(page: ft.Page) -> None:
    st = session(page)
    st["placeholder"] = None
    body = st.get("body")
    if body is None:
        return
    _, _, gap, cols, img_w = layout.metrics(page)
    items = st["items"]
    rows: list[ft.Control] = []
    for start in range(0, len(items), cols):
        row_items = items[start:start + cols]
        row_h = max(
            img_w / max(0.2, item.get("ratio", 0.7))
            for item in row_items
        )
        cells = []
        for item in row_items:
            holder = _image_holder(page, item, img_w)
            holder.opacity = 1.0
            cells.append(holder)
        rows.append(
            ft.Row(
                spacing=gap,
                alignment=ft.MainAxisAlignment.START,
                controls=cells,
            )
        )
        for cell in cells:
            cell.opacity = 1.0
    st["row_controls"] = list(rows)
    body.controls = rows
    try:
        body.update()
    except Exception:
        pass


def _image_holder(
    page: ft.Page,
    item: dict,
    img_w: float,
) -> ft.Container:
    height = img_w * 679 / 480
    inner = ft.Container(
        width=img_w,
        height=height,
        border_radius=8,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        scale=1.0,
        animate_scale=ft.Animation(
            160, ft.AnimationCurve.EASE_OUT
        ),
        content=(
            ft.Image(
                src=item["b64"],
                width=img_w,
                height=height,
                fit=ft.BoxFit.CONTAIN,
                gapless_playback=True,
            )
            if item.get("b64")
            else None
        ),
    )
    # 外层只占位、不裁剪；放大可覆盖相邻格子。
    return ft.Container(
        width=img_w,
        height=height,
        clip_behavior=ft.ClipBehavior.NONE,
        bgcolor=ft.Colors.TRANSPARENT,
        opacity=0.0,
        animate_opacity=ft.Animation(
            180, ft.AnimationCurve.EASE_OUT
        ),
        on_click=(
            lambda e, data=item.get("json") or {}: (
                open_random_detail(page, data)
            )
        ),
        content=hover_zoom(page, inner, scale=1.05),
    )


async def _fade_in(holder: ft.Container) -> None:
    await asyncio.sleep(0.016)
    holder.opacity = 1.0
    try:
        holder.update()
    except Exception:
        pass


def _cell_height(img_w: float) -> float:
    return img_w * 679 / 480


def _remove_placeholder(st: dict) -> None:
    """移除当前位置的加载转圈。"""
    data = st.pop("placeholder", None)
    if not isinstance(data, dict):
        return
    row = data.get("row")
    control = data.get("control")
    if row is None or control is None:
        return
    try:
        if control in row.controls:
            row.controls.remove(control)
            row.update()
    except Exception:
        pass


def _show_placeholder(page: ft.Page) -> None:
    """在下一张图的目标位置放一个加载转圈。"""
    st = session(page)
    body = st.get("body")
    if body is None:
        return
    _remove_placeholder(st)
    _, _, gap, cols, img_w = layout.metrics(page)
    index = len(st["items"])
    row_index = index // cols
    col = index % cols
    rows = st.setdefault("row_controls", [])
    created = False
    while len(rows) <= row_index:
        row = ft.Row(
            spacing=gap,
            alignment=ft.MainAxisAlignment.START,
            controls=[],
        )
        rows.append(row)
        body.controls.append(row)
        created = True
    row = rows[row_index]
    height = _cell_height(img_w)
    while len(row.controls) < col:
        row.controls.append(
            ft.Container(
                width=img_w,
                height=height,
                bgcolor=ft.Colors.TRANSPARENT,
            )
        )
    holder = ft.Container(
        width=img_w,
        height=height,
        alignment=ft.Alignment.CENTER,
        bgcolor=ft.Colors.TRANSPARENT,
        content=ft.ProgressRing(
            width=28,
            height=28,
            stroke_width=3,
        ),
    )
    row.controls.append(holder)
    try:
        (body if created else row).update()
    except Exception:
        pass
    st["placeholder"] = {
        "row": row,
        "control": holder,
        "index": index,
    }


def _finish_item(page: ft.Page, item: dict) -> None:
    """用图片替换占位转圈；没有占位时退回追加。"""
    st = session(page)
    data = st.pop("placeholder", None)
    if isinstance(data, dict):
        row = data.get("row")
        control = data.get("control")
        if row is not None and control in row.controls:
            _, _, _, _, img_w = layout.metrics(page)
            holder = _image_holder(page, item, img_w)
            try:
                row.controls[row.controls.index(control)] = holder
                row.update()
            except Exception:
                pass
            page.run_task(_fade_in, holder)
            return
    _append_item(page)


def _append_item(page: ft.Page) -> None:
    """只把最新图片追加到对应行，避免整页刷新。"""
    st = session(page)
    body = st.get("body")
    if body is None or not st["items"]:
        return
    _, _, gap, cols, img_w = layout.metrics(page)
    rows = st.setdefault("row_controls", [])
    if not rows or len(rows[-1].controls) >= cols:
        row = ft.Row(
            spacing=gap,
            alignment=ft.MainAxisAlignment.START,
            controls=[],
        )
        rows.append(row)
        body.controls.append(row)
        target: ft.Control = body
    else:
        row = rows[-1]
        target = row
    holder = _image_holder(page, st["items"][-1], img_w)
    row.controls.append(holder)
    try:
        target.update()
    except Exception:
        pass
    page.run_task(_fade_in, holder)


def _start_fill(page: ft.Page) -> None:
    st = session(page)
    view = st.get("view")
    if view is None:
        return
    st["token"] += 1
    token = st["token"]
    st["running"] = True

    def stop() -> None:
        if token == st["token"]:
            st["running"] = False

    async def run() -> None:
        while True:
            if token != st["token"]:
                return
            if not page.views or page.views[-1] is not view:
                stop()
                return
            _, height, gap, cols, img_w = layout.metrics(page)
            capacity = layout.capacity(
                st["items"], cols, img_w, gap, height
            )
            if len(st["items"]) >= capacity:
                stop()
                return
            _show_placeholder(page)
            started = time.monotonic()
            try:
                data = await asyncio.to_thread(_fetch_random, page)
                if token != st["token"]:
                    return
                mal_id = data.get("mal_id")
                seen = st.setdefault("seen_ids", set())
                if mal_id is not None and mal_id in seen:
                    _remove_placeholder(st)
                    elapsed = time.monotonic() - started
                    await asyncio.sleep(
                        max(0.0, REQUEST_INTERVAL - elapsed)
                    )
                    continue
                b64, ratio = await asyncio.to_thread(
                    _image_bytes, data
                )
                if token != st["token"]:
                    return
            except Exception:
                if token == st["token"]:
                    _remove_placeholder(st)
                    show_toast(page, "随机获取失败")
                    stop()
                return
            if mal_id is not None:
                seen.add(mal_id)
            item = {"b64": b64, "ratio": ratio, "json": data}
            st["items"].append(item)
            _finish_item(page, item)
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(0.0, REQUEST_INTERVAL - elapsed))

    page.run_task(run)


def _on_dice(page: ft.Page) -> None:
    st = session(page)
    st["token"] += 1
    st["items"] = []
    st["seen_ids"] = set()
    _render(page)
    _start_fill(page)


def _reset_random_session(st: dict) -> None:
    """随机页被移出视图栈时清空参数与图片缓存。"""
    if not isinstance(st, dict):
        return
    st["token"] += 1
    st["items"] = []
    st["seen_ids"] = set()
    st["placeholder"] = None
    st["refresh"] = False
    st["row_controls"] = []
    body = st.get("body")
    if body is not None:
        try:
            body.controls = []
            body.update()
        except Exception:
            pass
    st["body"] = None
    st["view"] = None


def _on_shown(page: ft.Page) -> None:
    """返回随机页：清掉 suppress；参数有改动才清空并重新随机。"""
    st = session(page)
    state = get_state(page)
    if state.suppress_auto_settings:
        state.suppress_auto_settings = False
    if state.params_dirty:
        state.params_dirty = False
        st["items"] = []
        st["seen_ids"] = set()
        _render(page)
        _start_fill(page)
        return
    # 返回随机页：未在填充且当前数量不足容量时继续补齐。
    if not st.get("running"):
        _, height, gap, cols, img_w = layout.metrics(page)
        capacity = layout.capacity(
            st["items"], cols, img_w, gap, height
        )
        if len(st["items"]) < capacity:
            _start_fill(page)


def _on_resize(page: ft.Page) -> None:
    """resize 防抖：只保留最后一次，0.12s 后重排。"""
    st = session(page)
    view = st.get("view")
    if not page.views or page.views[-1] is not view:
        return
    st["resize_token"] = st.get("resize_token", 0) + 1
    page.run_task(_apply_resize, page, st["resize_token"])


async def _apply_resize(page: ft.Page, token: int) -> None:
    await asyncio.sleep(0.12)
    st = session(page)
    if token != st.get("resize_token"):
        return
    view = st.get("view")
    if not page.views or page.views[-1] is not view:
        return
    # 每次都按当前窗口重新计算。
    _, height, gap, cols, img_w = layout.metrics(page)
    capacity = layout.capacity(
        st["items"], cols, img_w, gap, height
    )
    if len(st["items"]) > capacity:
        # 容量变小：截断并取消进行中的填充。
        st["items"] = st["items"][:capacity]
        st["token"] += 1
    _render(page)
    if len(st["items"]) < capacity:
        _start_fill(page)


def _schedule_settings(page: ft.Page) -> None:
    async def run() -> None:
        await asyncio.sleep(0.1)
        state = get_state(page)
        if state.suppress_auto_settings:
            state.suppress_auto_settings = False
            return
        open_random_settings(page)

    page.run_task(run)


def random_view(
    page: ft.Page,
    *,
    auto_settings: bool = True,
) -> ft.View:
    body = ft.Column(spacing=8, expand=True, controls=[])
    st = session(page)
    st["body"] = body
    st["view"] = None
    view = ft.View(
        route="/random",
        appbar=ft.AppBar(
            title=ft.Row(
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ui_text(
                        "随机",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    hover_icon(
                        page,
                        ft.Icons.CASINO,
                        tooltip="随机一次",
                        size=20,
                        padding=6,
                        on_click=lambda e: _on_dice(page),
                    ),
                    hover_icon(
                        page,
                        ft.Icons.SETTINGS,
                        tooltip="随机设置",
                        size=20,
                        padding=6,
                        on_click=lambda e: open_random_settings(page),
                    ),
                ],
            ),
            automatically_imply_leading=False,
            leading=back_icon(page, "/"),
        ),
        padding=page_padding(),
        controls=[
            ft.Column(
                expand=True,
                spacing=8,
                controls=[
                    body,
                ],
            )
        ],
    )
    st["view"] = view
    bind(view, page, st)
    data = view.data if isinstance(view.data, dict) else {}
    data["on_shown"] = lambda: _on_shown(page)
    data["on_close"] = lambda: _reset_random_session(st)
    view.data = data
    register_resize_handler(page, "/random", lambda e: _on_resize(page))
    _render(page)
    if auto_settings:
        _schedule_settings(page)
    return view


def open_random(page: ft.Page) -> None:
    """随机页与设置页一次入栈，避免视觉上连续切换两次。"""
    from bangumi.views.navigation.stack import (
        _run_navigation_hooks,
        sync_resize_subscription,
    )

    _run_navigation_hooks(page)
    random_page = random_view(page, auto_settings=False)
    # 先入栈随机页但不 update，让设置页构造时能取到同一份会话。
    page.views.append(random_page)
    settings_page = build_random_settings_view(page)
    page.views.append(settings_page)
    sync_resize_subscription(page)
    page.update()
