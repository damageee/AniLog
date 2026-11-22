"""从 長門番堂 (yuc.wiki) 抓取某一季度的新番标题。"""

from __future__ import annotations

import html
import re

from bangumi.services.proxy import http_get

SEASON_MONTHS = (1, 4, 7, 10)
EARLIEST_YEAR = 2019
EARLIEST_QUARTER = 3
REQUEST_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DETAIL_PATTERN = re.compile(
    r'class="title_cn[^>]*"[^>]*>(.*?)</p>',
    re.DOTALL,
)
TITLE_MAIN_PATTERN = re.compile(
    r'class="title_main[^"]*"[^>]*>(.*?)</td>',
    re.DOTALL,
)
TITLE_CN_PATTERN = re.compile(
    r'class="title_cn[^"]*"[^>]*>(.*?)</p>',
    re.DOTALL,
)
FUTURE_PATTERN = re.compile(
    r'class="future_title_"[^>]*>(.*?)</td>',
    re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")
FUTURE_URL = "https://yuc.wiki/new/"
FUTURE_MONTH_QUARTER = {1: 0, 4: 1, 7: 2, 10: 3}
FUTURE_INTRO_PATTERN = re.compile(
    r'class="future_intro"[^>]*>(.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)
FUTURE_TITLE_PATTERN = re.compile(
    r'class="future_title_[^"]*"[^>]*>(.*?)</td>',
    re.DOTALL | re.IGNORECASE,
)
FUTURE_MONTH_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月")
FUTURE_YEAR_PATTERN = re.compile(r"备战\s*(\d{4})")
BR_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)


class SeasonImportError(Exception):
    """季度列表无法获取或解析时抛出。"""


def season_url(year: int, index: int) -> str:
    """Return the 長門番堂 URL for a quarter (index: 0=冬 ... 3=秋)."""
    return f"https://yuc.wiki/{int(year)}{SEASON_MONTHS[int(index)]:02d}/"


def _supported(year: int, index: int) -> bool:
    if not 0 <= index < len(SEASON_MONTHS):
        return False
    return not (
        year < EARLIEST_YEAR
        or (year == EARLIEST_YEAR and index < EARLIEST_QUARTER)
    )


def _clean(text: str) -> str:
    value = TAG_PATTERN.sub("", text)
    value = html.unescape(value)
    return SPACE_PATTERN.sub(" ", value).strip()


def _clean_future(text: str) -> str:
    value = BR_PATTERN.sub(" ", text)
    value = TAG_PATTERN.sub("", value)
    value = html.unescape(value)
    return SPACE_PATTERN.sub(" ", value).strip()


def parse_titles(source: str) -> list[str]:
    """从季度页面收集中文标题，保持页面顺序。"""
    titles: list[str] = []
    seen: set[str] = set()

    def add(title: str) -> None:
        if not title or title in seen:
            return
        seen.add(title)
        titles.append(title)

    # 新版结构：一个 title_main 内可能有多行中文标题。
    main_found = False
    for match in TITLE_MAIN_PATTERN.finditer(source):
        main_found = True
        parts = [
            _clean(part)
            for part in TITLE_CN_PATTERN.findall(match.group(1))
        ]
        parts = [part for part in parts if part]
        if not parts:
            continue
        title = parts[0]
        for part in parts[1:]:
            if part.startswith(("(", "（", "[", "【")):
                title += part
            else:
                title += " " + part
        add(title)

    # 兼容旧结构：没有 title_main 时才逐条匹配。
    if not main_found:
        for match in DETAIL_PATTERN.finditer(source):
            add(_clean(match.group(1)))

    # 前瞻标题保持原有兼容。
    for match in FUTURE_PATTERN.finditer(source):
        add(_clean(match.group(1)))
    return titles


def _fetch_page(url: str) -> str:
    try:
        response = http_get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        if not response.encoding or (
            response.encoding.lower() == "iso-8859-1"
        ):
            response.encoding = response.apparent_encoding or "utf-8"
        source = response.text
    except Exception as error:
        raise SeasonImportError("request failed") from error
    if not source.strip():
        raise SeasonImportError("empty page")
    return source


def fetch_season_titles(year: int, index: int) -> list[str]:
    """返回该季度的标题；失败时抛出 SeasonImportError。"""
    try:
        year = int(year)
        index = int(index)
    except (TypeError, ValueError) as error:
        raise SeasonImportError("invalid quarter") from error
    if not _supported(year, index):
        raise SeasonImportError("quarter not covered by yuc.wiki")
    try:
        response = http_get(
            season_url(year, index),
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        if not response.encoding or (
            response.encoding.lower() == "iso-8859-1"
        ):
            response.encoding = response.apparent_encoding or "utf-8"
        source = response.text
    except Exception as error:
        raise SeasonImportError("request failed") from error
    if not source.strip():
        raise SeasonImportError("empty page")
    titles = parse_titles(source)
    if not titles:
        raise SeasonImportError("no titles parsed")
    return titles


def _future_label(heading: str) -> tuple[str, int, int] | None:
    from bangumi.data.quarter_core import quarter_label

    month_match = FUTURE_MONTH_PATTERN.search(heading)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        quarter = FUTURE_MONTH_QUARTER.get(month)
        if quarter is None:
            return None
        return (
            quarter_label(year, quarter),
            year,
            quarter,
        )
    year_match = FUTURE_YEAR_PATTERN.search(heading)
    if year_match:
        year = int(year_match.group(1))
        return (f"{year}+", year, 4)
    return None


def fetch_future_categories() -> dict[str, list[str]]:
    """Fetch future anime grouped by quarter/備戰 year from yuc.wiki/new."""
    source = _fetch_page(FUTURE_URL)
    matches = list(FUTURE_INTRO_PATTERN.finditer(source))
    if not matches:
        raise SeasonImportError("no future sections")
    entries: list[tuple[tuple[int, int], str, list[str]]] = []
    for index, match in enumerate(matches):
        heading = _clean_future(match.group(1))
        label = _future_label(heading)
        if label is None:
            continue
        name, year, quarter = label
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(source)
        )
        body = source[match.end():end]
        titles: list[str] = []
        seen: set[str] = set()
        for title_match in FUTURE_TITLE_PATTERN.finditer(body):
            title = _clean_future(title_match.group(1))
            if not title or title in seen:
                continue
            seen.add(title)
            titles.append(title)
        if titles:
            entries.append(((year, quarter), name, titles))
    if not entries:
        raise SeasonImportError("no future titles")
    entries.sort(key=lambda entry: entry[0])
    return {name: titles for _, name, titles in entries}
