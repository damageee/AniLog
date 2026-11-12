"""获取并规范化 Bangumi 条目的基础信息。

用法：
    python -m bangumi.services.bgm_info 225604

此处仅使用 /subjects/{id}。人物与角色分别位于
bgm_persons / bgm_characters，由调用方显式获取。

网络或格式问题不会抛出异常：而是返回带空值的固定映射。
"""

from __future__ import annotations

import json
import re
import sys

from bangumi.data.dates import format_display_date

import requests

from bangumi.services.bgm_search import (
    _user_agent,
    current_proxies,
    mark_proxy_dead,
)

API_ROOT = "https://api.bgm.tv/v0"
TIMEOUT = 10

_RUNTIME_MIN_RE = re.compile(r"\s*min(?:ute)?s?\b", re.IGNORECASE)
_RUNTIME_CN_RE = re.compile(r"(?<=\d)\s*分(?!钟)")


def _runtime_text(value: object) -> str:
    text = str(value or "").strip()
    text = _RUNTIME_MIN_RE.sub("分钟", text)
    return _RUNTIME_CN_RE.sub("分钟", text)


EMPTY_KEYS = (
    "规格",
    "类型",
    "TAG",
    "放送",
    "评分",
)

_REGION_TAGS = {
    "日本",
    "中国",
    "国产",
    "美国",
    "韩国",
    "欧美",
    "英国",
    "法国",
    "德国",
    "中国动画",
    "日本动画",
    "国产动画",
    "美国动画",
}
_FORMAT_TAGS = {"tv", "ova", "oad", "sp", "剧场版", "电影", "web"}
_TYPE_TAGS = ("原创", "小说改", "漫画改", "游戏改", "动画改", "影视改")
_TV_PLATFORM = "TV"
_OVA_PLATFORM = "OVA"
_MOVIE_PLATFORM = "剧场版"


def _empty_result() -> dict[str, object]:
    result = {key: [] if key == "TAG" else "" for key in EMPTY_KEYS}
    result["name_cn"] = ""
    result["error"] = ""
    return result


def _get_json(url: str) -> object | None:
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}
    kwargs = {"headers": headers, "timeout": TIMEOUT}
    try:
        response = requests.get(
            url,
            proxies=current_proxies(),
            **kwargs,
        )
    except requests.exceptions.ProxyError:
        mark_proxy_dead()
        try:
            response = requests.get(
                url,
                proxies={"http": None, "https": None},
                **kwargs,
            )
        except Exception:
            return None
    except Exception:
        return None
    try:
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _get_json_with_error(url: str) -> tuple[object | None, str]:
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}
    kwargs = {"headers": headers, "timeout": TIMEOUT}
    try:
        response = requests.get(
            url,
            proxies=current_proxies(),
            **kwargs,
        )
    except requests.exceptions.ProxyError:
        mark_proxy_dead()
        try:
            response = requests.get(
                url,
                proxies={"http": None, "https": None},
                **kwargs,
            )
        except Exception:
            return None, "网络请求失败"
    except Exception:
        return None, "网络请求失败"
    if response.status_code == 404:
        return None, "条目不存在"
    if not 200 <= response.status_code < 300:
        return None, f"接口返回 {response.status_code}"
    try:
        return response.json(), ""
    except Exception:
        return None, "返回数据格式错误"


def _infobox_value(value: object) -> str:
    if isinstance(value, list):
        parts = [
            str(item.get("v") or "").strip()
            for item in value
            if isinstance(item, dict) and item.get("v")
        ]
        return "、".join(part for part in parts if part)
    return str(value or "").strip()


def _infobox_map(infobox: object) -> dict[str, str]:
    result: dict[str, str] = {}
    if not isinstance(infobox, list):
        return result
    for item in infobox:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key or key in result:
            continue
        result[key] = _infobox_value(item.get("value"))
    return result


def _first(info: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = info.get(key, "").strip()
        if value:
            return value
    return ""


def _digits(value: object) -> str:
    text = str(value or "").strip()
    match = re.search(r"\d+", text)
    return match.group(0) if match else text


def _format_date(value: object) -> str:
    return format_display_date(value)


def _clean_meta_tags(tags: object) -> tuple[str, list[str]]:
    kind = ""
    remaining: list[str] = []
    seen: set[str] = set()
    if not isinstance(tags, list):
        return kind, remaining
    for raw in tags:
        tag = str(raw or "").strip()
        if not tag:
            continue
        folded = tag.casefold()
        if tag in _REGION_TAGS or folded in {
            value.casefold() for value in _REGION_TAGS
        }:
            continue
        if folded in _FORMAT_TAGS:
            continue
        if tag in _TYPE_TAGS:
            if not kind:
                kind = tag
            continue
        if folded in seen:
            continue
        seen.add(folded)
        remaining.append(tag)
    return kind, remaining


def _specification(
    platform: str,
    episodes: str,
    runtime: str,
) -> str:
    if platform == _TV_PLATFORM:
        return f"{episodes}话" if episodes else ""
    if platform == _OVA_PLATFORM:
        if not episodes or episodes == "1":
            return "OVA"
        return f"{episodes}OVA"
    if platform == _MOVIE_PLATFORM:
        return runtime or episodes
    return ""


def _category(
    kind: str,
    platform: str,
    original_name: object = "",
    name_cn: object = "",
) -> str:
    text = f"{original_name or ''}{name_cn or ''}"
    if "剧场版" in text or "劇場版" in text:
        return kind
    if platform == _MOVIE_PLATFORM and kind == "原创":
        return "电影"
    if not kind or kind in ("动画改", "影视改"):
        return "其他"
    return kind


def _rating(value: object) -> object:
    if not isinstance(value, dict):
        return ""
    score = value.get("score")
    if not isinstance(score, (int, float)) or score <= 0:
        return ""
    return int(score * 10)


def get_subject_info(
    subject_id: int | str,
    original_name: str = "",
) -> dict[str, object]:
    """返回单个 Bangumi 条目的固定规范化映射。"""
    result = _empty_result()
    try:
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return result

    base = f"{API_ROOT}/subjects/{subject_id}"
    subject, error = _get_json_with_error(base)
    if error:
        return {**_empty_result(), "error": error}
    if not isinstance(subject, dict):
        return {**_empty_result(), "error": "条目数据无效"}
    try:
        is_anime = int(subject.get("type")) == 2
    except (TypeError, ValueError):
        is_anime = False
    if not is_anime:
        return {**_empty_result(), "error": "不是动画条目"}

    info = _infobox_map(subject.get("infobox"))
    result["name_cn"] = str(
        subject.get("name_cn") or subject.get("name") or ""
    ).strip()
    platform = str(subject.get("platform") or "").strip()
    episodes = _digits(
        info.get("话数") or subject.get("total_episodes")
    )
    runtime = _runtime_text(info.get("片长", ""))
    date0 = _first(info, "发售日", "上映年度", "放送开始")
    date1 = _first(info, "播放结束", "放送结束")
    kind, tags = _clean_meta_tags(subject.get("meta_tags"))

    date0_text = _format_date(date0)
    date1_text = _format_date(date1)
    if date1_text:
        broadcast = f"{date0_text}~{date1_text}"
    else:
        broadcast = date0_text

    result["规格"] = _specification(platform, episodes, runtime)
    result["类型"] = _category(
        kind,
        platform,
        original_name,
        result.get("name_cn"),
    )
    result["TAG"] = tags
    result["放送"] = broadcast
    result["评分"] = _rating(subject.get("rating"))
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        return 1
    try:
        subject_id = int(args[0])
    except ValueError:
        return 1
    print(
        json.dumps(
            get_subject_info(subject_id),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
