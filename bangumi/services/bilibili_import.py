"""Bilibili 追番导入（服务层）。"""

from __future__ import annotations

from bangumi.services.proxy import http_get
from bangumi.views.watchlist.constants import (
    BILIBILI_FOLLOW_URL,
    BILIBILI_HEADERS,
    BILIBILI_PAGE_SIZE,
    BILIBILI_TIMEOUT,
)
from bangumi.views.watchlist.utils import (
    clean_bilibili_title,
    has_animation_style,
)

# Bilibili follow_status：1=想看，2=在看，3=看过
WANT_TO_WATCH = 1
WATCHING = 2
WATCHED = 3


class BilibiliImportError(Exception):
    """面向用户的 Bilibili 导入失败。"""


def fetch_bilibili_following(
    uid: str,
    statuses: set[int],
) -> list[str]:
    """返回该用户处于 statuses 中任一状态的番剧 / 影视标题。"""
    allowed = set(statuses)
    titles: list[str] = []
    seen: set[str] = set()
    headers = dict(BILIBILI_HEADERS)
    headers["Referer"] = (
        f"https://space.bilibili.com/{uid}/bangumi"
    )
    # follow_type：1=番剧，2=影视；影视只保留动画风格条目。
    for follow_type, anime_only in ((1, False), (2, True)):
        pn = 1
        while True:
            response = http_get(
                BILIBILI_FOLLOW_URL,
                params={
                    "type": follow_type,
                    # 请求全量，状态在本地按 allowed 过滤。
                    "follow_status": 0,
                    "pn": pn,
                    "ps": BILIBILI_PAGE_SIZE,
                    "vmid": uid,
                },
                headers=headers,
                timeout=BILIBILI_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            code = payload.get("code")
            data = payload.get("data")
            if code == -400:
                raise BilibiliImportError(
                    "UID 格式不正确或请求失败"
                )
            if code == 53013:
                raise BilibiliImportError(
                    "用户不存在或追番列表未公开"
                )
            if code != 0:
                raise BilibiliImportError(
                    str(payload.get("message") or "导入失败")
                )
            if not data:
                raise BilibiliImportError(
                    "用户不存在或追番列表未公开"
                )

            total = int(data.get("total") or 0)
            items = data.get("list") or []
            if not items:
                break
            for item in items:
                # 只有状态不在给定集合里才跳过。
                if item.get("follow_status") not in allowed:
                    continue
                if anime_only and not has_animation_style(item):
                    continue
                title = clean_bilibili_title(item.get("title"))
                if not title or title in seen:
                    continue
                seen.add(title)
                titles.append(title)

            if total <= 0 or pn * BILIBILI_PAGE_SIZE >= total:
                break
            pn += 1
    return titles


