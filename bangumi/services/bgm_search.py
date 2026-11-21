"""在 Bangumi 中按名称搜索动画条目。

公开入口为 :func:`search_bgm`：传入 动画 值，返回按分数排序的条目字典列表。
每次调用只发一次 API 请求（不请求详情/别名）；网络失败时返回空列表。
"""

from __future__ import annotations

import math
import os
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import requests

from bangumi.core.text_variants import fold_variants
from bangumi.services.proxy import current_proxies, mark_proxy_dead

V0_SEARCH_URL = "https://api.bgm.tv/v0/search/subjects"
V0_LIMIT = 10
ALIAS_TOP_N = 0  # 详情/别名有意禁用
TIMEOUT = 10
POSITION_BONUSES = [0.30, 0.25, 0.20, 0.15, 0.10, 0.0, 0.0, 0.0, 0.0, 0.0]
PART_PENALTY = 0.50
SPACE_PENALTY = 0.50
COVERAGE_THRESHOLD = 0.50
COVERAGE_PENALTY = 0.30
EXACT_SCORE = 0.98
STRONG_SCORE = 0.85
ACCEPT_SCORE = 0.10
NON_EXACT_CAP = 0.99

ABBREVIATIONS: dict[str, str] = {
    "火影": "火影忍者",
    "海贼王": "航海王",
    "柯南": "名侦探柯南",
    "龙珠": "七龙珠",
    "灌篮": "灌篮高手",
    "美战": "美少女战士",
    "数码宝贝": "数码宝贝大冒险",
    "宝可梦": "精灵宝可梦",
    "游戏王": "游戏王决斗怪兽",
    "EVA": "新世纪福音战士",
    "高达": "机动战士高达",
    "进巨": "进击的巨人",
    "钢炼": "钢之炼金术师",
    "死笔": "死亡笔记",
    "鲁路修": "叛逆的鲁路修",
    "小圆": "魔法少女小圆",
    "石头门": "命运石之门",
    "刀剑": "刀剑神域",
    "喰种": "东京喰种",
    "一拳": "一拳超人",
    "小英雄": "我的英雄学院",
    "鬼灭": "鬼灭之刃",
    "咒术": "咒术回战",
    "间谍": "间谍过家家",
    "芙莉莲": "葬送的芙莉莲",
    "辉夜": "辉夜大小姐想让我告白",
    "青猪": "青春猪头少年不会梦到兔女郎学姐",
    "春物": "我的青春恋爱物语果然有问题",
    "路人女主": "路人女主的养成方法",
    "紫罗兰": "紫罗兰永恒花园",
    "君名": "你的名字。",
    "天子": "天气之子",
    "铃芽": "铃芽之旅",
    "千寻": "千与千寻",
    "哈尔": "哈尔的移动城堡",
    "凉宫": "凉宫春日的忧郁",
    "轻音": "轻音少女",
    "超炮": "某科学的超电磁炮",
    "魔禁": "魔法禁书目录",
    "夏目": "夏目友人帐",
    "四谎": "四月是你的谎言",
    "花名": "我们仍未知道那天所看见的花的名字",
    "未闻花名": "我们仍未知道那天所看见的花的名字",
    "排球": "排球少年",
    "黑篮": "黑子的篮球",
    "网王": "网球王子",
    "齐神": "齐木楠雄的灾难",
    "灵能": "灵能百分百",
    "刀乱": "刀剑乱舞",
    "文豪": "文豪野犬",
    "史莱姆": "关于我转生变成史莱姆这档事",
    "骨王": "不死者之王",
    "无职": "无职转生",
    "盾勇": "盾之勇者成名录",
    "慎勇": "这个勇者明明超强却过分慎重",
    "萌王": "关于我转生变成史莱姆这档事",
    "约战": "约会大作战",
    "魔劣": "魔法科高中的劣等生",
    "落第": "落第骑士英雄谭",
    "学战": "学战都市Asterisk",
    "极黑": "极黑的布伦希尔德",
    "漆黑": "漆黑的子弹",
    "斩瞳": "斩！赤红之瞳",
    "食尸鬼": "东京喰种",
    "东京食尸鬼": "东京喰种",
    "甲铁城": "甲铁城的卡巴内利",
    "甲铁城的卡巴内瑞": "甲铁城的卡巴内利",
    "心测": "心理测量者",
    "天使心跳": "天使的心跳",
    "黑契": "黑之契约者",
    "末日三问": "末日时在做什么？有没有空？可以来拯救吗？",
    "re0": "Re：从零开始的异世界生活",
    "电锯人": "链锯人",
    "gbc": "少女乐队的呐喊",
    "girls band cry": "少女乐队的呐喊",
    "废渊战鬼": "咔嗒咔嗒",
    "angels of death": "杀戮天使",
    "杀戮的天使": "杀戮天使",
    "蔚蓝档案 The Animation": "蔚蓝档案 动画版",
    "Dr.STONE 石纪元":"石纪元",
    "黑执事 Book of Circus": "黑执事 马戏团篇",
    "黑执事 Book of Murder": "黑执事 幽鬼城杀人事件篇",
    "黑执事 Book of the Atlantic": "黑执事 豪华客船篇",
    "剧场版 黑执事 Book of the Atlantic": "黑执事 豪华客船篇",
    "地错": "在地下城寻求邂逅是否搞错了什么",
    "轻音少女!": "轻音少女",
    "轻音少女！": "轻音少女",
    "轻音少女!!": "轻音少女 第二季",
    "轻音少女！！": "轻音少女 第二季",
    "大叔转生恶役大小姐": "中年上班族转生恶役",

}

NAME_IDS: dict[str, int] = {
    "名侦探柯南": 899,
    "灌篮高手": 1608,
    "美少女战士": 1510,
    "数码宝贝大冒险": 3128,
    "游戏王决斗怪兽": 6390,
    "新世纪福音战士": 265,
    "机动战士高达": 50,
    "进击的巨人": 55770,
    "钢之炼金术师": 315,
    "死亡笔记": 1773,
    "魔法少女小圆": 9717,
    "命运石之门": 10380,
    "刀剑神域": 23686,
    "东京喰种": 93714,
    "一拳超人": 127563,
    "我的英雄学院": 150955,
    "鬼灭之刃": 245665,
    "咒术回战": 294993,
    "间谍过家家": 329906,
    "葬送的芙莉莲": 400602,
    "辉夜大小姐想让我告白": 248175,
    "青春猪头少年不会梦到兔女郎学姐": 240038,
    "我的青春恋爱物语果然有问题": 54433,
    "路人女主的养成方法": 100403,
    "紫罗兰永恒花园": 183878,
    "你的名字。": 160209,
    "天气之子": 269235,
    "铃芽之旅": 362577,
    "千与千寻": 311,
    "哈尔的移动城堡": 312,
    "凉宫春日的忧郁": 485,
    "轻音少女": 1424,
    "某科学的超电磁炮": 2585,
    "魔法禁书目录": 1014,
    "夏目友人帐": 259,
    "四月是你的谎言": 100444,
    "我们仍未知道那天所看见的花的名字": 10440,
    "排球少年": 84171,
    "黑子的篮球": 23684,
    "网球王子": 1939,
    "齐木楠雄的灾难": 80932,
    "灵能百分百": 158316,
    "文豪野犬": 144357,
    "关于我转生变成史莱姆这档事": 239816,
    "盾之勇者成名录": 217660,
    "约会大作战": 49131,
    "魔法科高中的劣等生": 84872,
    "落第骑士英雄谭": 127724,
    "极黑的布伦希尔德": 89485,
    "漆黑的子弹": 84873,
    "斩！赤红之瞳": 94244,
    "甲铁城的卡巴内利": 118781,
    "心理测量者": 37685,
    "天使的心跳": 1851,
    "末日时在做什么？有没有空？可以来拯救吗？": 185943,
    "刀剑乱舞-花丸-": 175525,
    "宝可梦": 3019,
    "OVERLORD": 112146,
    "反叛的鲁路修": 793,
    "Code Geass 反叛的鲁路修": 793,
    "慎重勇者 ～这个勇者明明超强却过分慎重～": 266157,
    "学战都市 六芒星": 130250,
    "DARKER THAN BLACK -黑之契约者-": 292,
    "无职转生～到了异世界就拿出真本事～": 277554,
    "航海王": 975,
    "刀剑乱舞": 175525,
    "精灵宝可梦": 3019,
    "不死者之王": 112146,
    "叛逆的鲁路修": 793,
    "这个勇者明明超强却过分慎重": 266157,
    "学战都市Asterisk": 130250,
    "黑之契约者": 292,
    "火影忍者": 3425,
    "无职转生": 277554,
    "七龙珠": 9565,
    "龙珠": 9565,
    "Re：从零开始的异世界生活": 140001,
    "链锯人": 321885,
    "少女乐队的呐喊": 431767,
    "咔嗒咔嗒": 498947,
    "杀戮天使": 220566,
    "蔚蓝档案 动画版": 416777,
    "石纪元": 266794,
    "黑执事 马戏团篇": 100526,
    "黑执事 幽鬼城杀人事件篇": 100511,
    "黑执事 豪华客船篇": 148389,
    "在地下城寻求邂逅是否搞错了什么": 116287,
    "轻音少女": 1424,
    "轻音少女 第二季": 3774,
    "中年上班族转生恶役": 473497,
}

USER_AGENT_TEMPLATE = (
    "damage/AniLog/{version} ({platform}) "
    "(https://github.com/damageee/AniLog)"
)
PROJECT_URL = "https://bgm.tv/subject/{subject_id}"

def _clean_keyword(value: object) -> str:
    return " ".join(str(value or "").split())

_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_HANZI_RE = re.compile(r"[\u4e00-\u9fff]")
_LOOSE_STRIP = set("篇第期季 ")
_SEASON_STRIP_RE = re.compile(
    r"第?[0-9一二三四五六七八九十]+(?:季度|季|部分|部|期|章)"
    r"|season[0-9]+"
    r"|[0-9]+(?:st|nd|rd|th)season"
    r"|最终章|剧场版|特别篇",
    re.IGNORECASE,
)
_PART_NUM_RE = re.compile(
    r"(?:第)?([0-9]+|[一二三四五六七八九十]+)(?:季度|季|期|部|章)"
)
_SEASON_EN_RE = re.compile(r"season([0-9]+)", re.IGNORECASE)
_ORDINAL_EN_RE = re.compile(
    r"([0-9]+)(?:st|nd|rd|th)season",
    re.IGNORECASE,
)
_SPECIAL_PART_RE = re.compile(r"最终章|剧场版|特别篇")
_SPACE_IGNORE_RE = re.compile(
    r"第?[0-9一二三四五六七八九十]+(?:季度|季|期|部分|部|章)"
    r"|season\s*[0-9]+"
    r"|[0-9]+(?:st|nd|rd|th)\s*season"
    r"|part\s*[.\-]?\s*[0-9]+"
    r"|剧场版|电影|OVA|OAD|SP|特别篇",
    re.IGNORECASE,
)

_PARTICLES = set(
    "的地得了着过是在和与及或而就都也还又很太更最把被让对给从向到于为以之其这那有"
    "のをにはがでともへや"
)
_CN_DIGITS = "零一二三四五六七八九"


def _project_version() -> str:
    """从 pyproject.toml 读取版本，失败时回退到 0.2.0。"""
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "0.1.0"
    match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "0.2.0"


def _platform_name() -> str:
    env = os.environ.get("FLET_PLATFORM", "")
    if env.lower().startswith("android") or sys.platform == "android":
        return "Android"
    return "Windows"


def _user_agent() -> str:
    return USER_AGENT_TEMPLATE.format(
        version=_project_version(),
        platform=_platform_name(),
    )


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("季度", "部分")
    text = fold_variants(text)
    return "".join(
        char for char in text.casefold() if not char.isspace()
    )


def _query_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    kept = "".join(
        char if char.isalnum() else " " for char in text
    )
    return " ".join(kept.split())


_ALIAS_STRIP_RE = re.compile(
    r"第?\s*[0-9一二三四五六七八九十]+\s*(?:季度|季|部分|部|期|章)"
    r"|(?<![A-Za-z])season\s*[0-9]*(?![A-Za-z])"
    r"|[0-9]+\s*(?:st|nd|rd|th)\s*season\b"
    r"|(?<![A-Za-z])part\s*[.\-]?\s*[0-9]*(?![A-Za-z])"
    r"|最终季|最终章|剧场版|电影|特别篇"
    r"|(?<![A-Za-z0-9])(?:OVA|OAD|SP)[0-9]*(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _alias_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = _ALIAS_STRIP_RE.sub(" ", text)
    text = _normalize(text)
    text = re.sub(r"[0-9]+", "", text)
    return text.lower()


def _expand_abbreviation(keyword: str) -> str:
    key = _alias_key(_season_rules(keyword))
    if not key:
        return keyword
    for abbr, full in ABBREVIATIONS.items():
        if _alias_key(abbr) != key:
            continue
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)
        expanded, count = pattern.subn(full, keyword, count=1)
        if count:
            return expanded
    return keyword


def _loose(value: object) -> str:
    return "".join(
        char for char in _normalize(value) if char not in _LOOSE_STRIP
    )


def _strip_season(value: object) -> str:
    return _SEASON_STRIP_RE.sub("", _normalize(value))


def _multiset(value: object) -> Counter[str]:
    text = _strip_season(value)
    return Counter(char for char in text if char not in _PARTICLES)


_ALPHA_RE = re.compile(r"[A-Za-z]+")


def _word_parts(value: object) -> list[str]:
    text = _SPACE_IGNORE_RE.sub(" ", str(value or ""))
    parts: list[str] = []
    for token in text.split():
        core = token.strip(
            "[](){}<>【】（）「」『』"
            "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~·・—–…“”‘’"
        )
        if any(char.isalnum() for char in core):
            parts.append(core)
    return parts


def _space_segment_mismatch(keyword: str, title: str) -> bool:
    key_parts = _word_parts(keyword)
    title_parts = _word_parts(title)
    if not key_parts or not title_parts:
        return False
    return len(key_parts) != len(title_parts)


def _alpha_words(value: object) -> list[str]:
    return _ALPHA_RE.findall(str(value or ""))


def _acronym(words: list[str]) -> str:
    return "".join(word[0] for word in words).casefold()


def _abbrev_match(keyword: str, title: str) -> bool:
    q_tokens = [
        _normalize(token)
        for token in str(keyword or "").split()
        if _normalize(token)
    ]
    t_tokens = [
        _normalize(token)
        for token in str(title or "").split()
        if _normalize(token)
    ]
    if not q_tokens or not t_tokens:
        return False

    q_letters = "".join(q_tokens)
    title_words = _alpha_words(title)
    if q_letters.isalpha() and title_words and _acronym(title_words) == q_letters:
        return True

    for index, q_token in enumerate(q_tokens):
        if not q_token.isalpha() or len(q_token) < 2:
            continue
        rest = q_tokens[:index] + q_tokens[index + 1 :]
        for start in range(len(t_tokens)):
            for end in range(start + 1, len(t_tokens) + 1):
                slice_words: list[str] = []
                for token in t_tokens[start:end]:
                    slice_words.extend(_alpha_words(token))
                if not slice_words or _acronym(slice_words) != q_token:
                    continue
                if t_tokens[:start] + t_tokens[end:] == rest:
                    return True
    return False


def _cn_to_int(text: str) -> int | None:
    digits = {
        char: index for index, char in enumerate(_CN_DIGITS) if index
    }
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(text) == 1:
        return digits.get(text)
    return None


def _digits_to_cn(text: str) -> str | None:
    if not text.isdigit():
        return None
    value = int(text)
    if value < 10:
        return _CN_DIGITS[value]
    if value == 10:
        return "十"
    if value < 20:
        return "十" + _CN_DIGITS[value - 10]
    if value < 100:
        tens = "" if value // 10 == 1 else _CN_DIGITS[value // 10]
        ones = "" if value % 10 == 0 else _CN_DIGITS[value % 10]
        return f"{tens}十{ones}"
    return None


_ORDINAL_TOKEN = r"[0-9]{1,2}|[Ⅰ-Ⅻ]+|[IVXLCDM]+"
_TRAILING_ORDINAL_RE = re.compile(
    rf"(?<![0-9])(?P<ord>{_ORDINAL_TOKEN})\s*$"
)
_SEASON_TAIL_ORDINAL_RE = re.compile(
    rf"(?P<season>第?\s*(?:[0-9]{{1,2}}|[一二三四五六七八九十]{{1,3}})\s*(?:季|期))"
    rf"\s*(?<![0-9])(?P<ord>{_ORDINAL_TOKEN})\s*$"
)
_SEASON_MARKER_RE = re.compile(
    r"第?\s*(?P<num>[0-9]{1,2}|[一二三四五六七八九十]{1,3})\s*"
    r"(?P<kind>季度|部分|季|期)",
    re.IGNORECASE,
)
_EN_SEASON_RE = re.compile(
    r"season\s*[0-9]*"
    r"|[0-9]+\s*(?:st|nd|rd|th)\s*season"
    r"|part\s*[.\-]?\s*[0-9]*",
    re.IGNORECASE,
)


def _tidy(value: object) -> str:
    return " ".join(str(value or "").split())


_ROMAN_VALUES = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}


def _roman_value(text: str) -> int | None:
    total = 0
    previous = 0
    for char in reversed(text):
        value = _ROMAN_VALUES[char]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def _ordinal_value(token: object) -> int | None:
    text = unicodedata.normalize("NFKC", str(token or "")).strip()
    if not text:
        return None
    if text.isdigit():
        value = int(text)
    elif re.fullmatch(r"[IVXLCDM]+", text):
        value = _roman_value(text)
    else:
        value = _cn_to_int(text)
    if value is None or not 1 <= value <= 30:
        return None
    return value


def _season_rules(value: object) -> str:
    text = _tidy(value)
    if not text:
        return text

    removals: list[tuple[int, int]] = []
    preserved = None          # 规则3 里紧挨裸序号、要原样保留的季/期标记
    season_mark = None
    part_mark = None
    season_tail = None
    part_tail = None
    part_from_tail = False

    # 规则3：结尾是「第?N季/期」+ 裸序号
    tail = _SEASON_TAIL_ORDINAL_RE.search(text)
    if tail is not None:
        number = _ordinal_value(tail.group("ord"))
        if number is not None:
            part_tail = number
            part_from_tail = True
            preserved = tail.start("season")
            removals.append((tail.start("ord"), tail.end("ord")))
    else:
        # 规则2：结尾是裸序号
        ordinal = _TRAILING_ORDINAL_RE.search(text)
        if ordinal is not None:
            number = _ordinal_value(ordinal.group("ord"))
            if number is not None:
                season_tail = number
                removals.append((ordinal.start(), ordinal.end()))

    # 规则1：去掉所有季/部分标记，并记录最后一个季号/部分号
    for match in _SEASON_MARKER_RE.finditer(text):
        if preserved is not None and match.start() == preserved:
            continue
        number = _ordinal_value(match.group("num"))
        if number is None:
            continue
        removals.append((match.start(), match.end()))
        if match.group("kind") in ("季度", "部分"):
            part_mark = number
        else:
            season_mark = number

    for match in _EN_SEASON_RE.finditer(text):
        removals.append((match.start(), match.end()))

    season_no = season_mark if season_mark is not None else season_tail
    part_no = part_mark if part_mark is not None else part_tail
    append_tail_part = part_mark is None and part_from_tail

    removals.sort()
    pieces: list[str] = []
    cursor = 0
    for start, end in removals:
        if start < cursor:
            continue
        pieces.append(text[cursor:start])
        pieces.append(" ")
        cursor = end
    pieces.append(text[cursor:])
    base = _tidy("".join(pieces))
    if not base:
        return text

    if season_no is not None and season_no >= 2:
        cn = _digits_to_cn(str(season_no)) or str(season_no)
        base = f"{base} 第{cn}季"
    if part_no is not None and (part_no >= 2 or append_tail_part):
        cn = _digits_to_cn(str(part_no)) or str(part_no)
        base = f"{base} 第{cn}部分"
    return _tidy(base)


def _part_info(value: object) -> tuple[int | None, bool]:
    """返回标题/关键词的 ``(part_number, has_special_marker)``。"""
    text = str(value or "")
    match = _PART_NUM_RE.search(text)
    if match is not None:
        raw = match.group(1)
        number = int(raw) if raw.isdigit() else _cn_to_int(raw)
        return number, False
    match = _SEASON_EN_RE.search(text)
    if match is not None:
        return int(match.group(1)), False
    match = _ORDINAL_EN_RE.search(text)
    if match is not None:
        return int(match.group(1)), False
    return None, bool(_SPECIAL_PART_RE.search(text))


def _part_penalty(keyword: str, title: str) -> float:
    keyword_number, keyword_special = _part_info(keyword)
    title_number, title_special = _part_info(title)
    if keyword_number is not None:
        if title_number == keyword_number:
            return 1.0
        return PART_PENALTY
    if keyword_special:
        return 1.0 if title_special else PART_PENALTY
    if title_number is not None or title_special:
        return PART_PENALTY
    return 1.0


def _query_variants(keyword: str) -> list[str]:
    variants = [keyword]
    match = _PART_NUM_RE.search(keyword)
    if match is None:
        return variants
    number = match.group(1)
    start, end = match.start(1), match.end(1)
    has_prefix = match.group(0).startswith("第")
    if not has_prefix:
        variants.append(keyword[:start] + "第" + keyword[start:])
    chinese = _digits_to_cn(number)
    if chinese is not None:
        variants.append(keyword[:start] + chinese + keyword[end:])
        if not has_prefix:
            variants.append(
                keyword[:start] + "第" + chinese + keyword[end:]
            )
    unique: list[str] = []
    for variant in variants:
        if variant and variant not in unique:
            unique.append(variant)
    return unique


def _base_score(query: str, title: str) -> float:
    q = _normalize(query)
    t = _normalize(title)
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    if (
        not _KANA_RE.search(q)
        and not _KANA_RE.search(t)
        and _multiset(q) == _multiset(t)
    ):
        return 1.0
    if t.startswith(q):
        return 0.80
    if q.startswith(t):
        return 0.70
    if q in t:
        return 0.80
    return 0.85 * SequenceMatcher(None, q, t).ratio()


def _coverage(query: str, title: str) -> float | None:
    hanzi = [
        char
        for char in str(query or "")
        if _HANZI_RE.fullmatch(char) and char not in _PARTICLES
    ]
    unique = list(dict.fromkeys(hanzi))
    if len(unique) < 2:
        return None
    normalized_title = _normalize(title)
    if not normalized_title:
        return 0.0
    matched = sum(1 for char in unique if char in normalized_title)
    return matched / len(unique)


def _title_score(
    keyword: str,
    variants: list[str],
    title: str,
) -> tuple[float, bool]:
    """返回单个候选标题的 ``(score, exact)``。"""
    normalized_keyword = _normalize(keyword)
    normalized_title = _normalize(title)
    if not normalized_title:
        return 0.0, False
    if normalized_keyword and normalized_keyword == normalized_title:
        return 1.0, True
    loose_keyword = _loose(keyword)
    loose_title = _loose(title)
    if loose_keyword and loose_keyword == loose_title:
        return 0.99, True

    base = max(
        _base_score(variant, title) for variant in variants
    )
    if base >= 1.0:
        keyword_number, _ = _part_info(keyword)
        title_number, title_special = _part_info(title)
        if keyword_number is None or title_number == keyword_number:
            return 1.0, True
        if (
            title_number is None
            and not title_special
            and keyword_number == 1
        ):
            return 1.0, True
        return PART_PENALTY, False

    abbrev = _abbrev_match(keyword, title)
    if abbrev:
        base = max(base, 0.99)
    elif _space_segment_mismatch(keyword, title):
        base *= SPACE_PENALTY

    coverage = _coverage(keyword, title)
    if coverage is not None:
        if coverage <= COVERAGE_THRESHOLD:
            base *= COVERAGE_PENALTY
        elif coverage >= 0.8:
            bonus = 0.1 * math.pow(2.0, (coverage - 0.8) / 0.2)
            base = min(1.0, base + bonus)
    base *= _part_penalty(keyword, title)
    return min(base, NON_EXACT_CAP), False


def _confidence(score: float, exact: bool) -> str:
    if exact or score >= EXACT_SCORE:
        return "exact"
    if score >= STRONG_SCORE:
        return "strong"
    return "fallback"


def _post_search(keyword: str) -> dict[str, object] | None:
    payload = {
        "keyword": keyword,
        "sort": "match",
        "filter": {"type": [2]},
    }
    headers = {
        "User-Agent": _user_agent(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    kwargs = {
        "params": {"limit": V0_LIMIT},
        "json": payload,
        "headers": headers,
        "timeout": TIMEOUT,
    }
    try:
        response = requests.post(
            V0_SEARCH_URL,
            proxies=current_proxies(),
            **kwargs,
        )
    except requests.exceptions.ProxyError:
        mark_proxy_dead()
        response = requests.post(
            V0_SEARCH_URL,
            proxies={"http": None, "https": None},
            **kwargs,
        )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        return data
    return None


_MOVIE_WORDS_RE = re.compile(r"剧场版|劇場版|电影")
_ROMAN_RE = re.compile(
    r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]"
    r"|(?<![A-Za-z0-9])[IVXLCDM]+(?![A-Za-z0-9])"
)


def _strip_movie_words(value: str) -> str:
    return " ".join(
        _MOVIE_WORDS_RE.sub(" ", str(value or "")).split()
    )


def _score_items(
    items: list,
    scoring_keyword: str,
) -> list[tuple[dict[str, object], float, bool]]:
    variants = _query_variants(scoring_keyword)
    scored: list[tuple[dict[str, object], float, bool]] = []
    for position, item in enumerate(items[:V0_LIMIT]):
        if not isinstance(item, dict):
            continue
        subject_id = item.get("id")
        if not isinstance(subject_id, int):
            continue
        name = str(item.get("name") or "")
        name_cn = str(item.get("name_cn") or "").strip() or name
        name_cn = _season_rules(name_cn)
        titles = [
            title
            for title in dict.fromkeys((name, name_cn))
            if title
        ]
        title_scores = [
            _title_score(scoring_keyword, variants, title)
            for title in titles
        ]
        if not title_scores:
            continue
        score, exact = max(title_scores)
        if score <= 0.0:
            continue
        bonus = (
            POSITION_BONUSES[position]
            if position < len(POSITION_BONUSES)
            else 0.0
        )
        scored.append((item, score + bonus, exact))

    if len(items) < 5 and all(
        score < 0.7 for _, score, _ in scored
    ):
        fixed_scores = [0.8, 0.75, 0.72, 0.7, 0.6]
        scored = [
            (
                item,
                (
                    fixed_scores[position]
                    if position < len(fixed_scores)
                    else 0.0
                ),
                False,
            )
            for position, item in enumerate(items)
            if isinstance(item, dict)
            and isinstance(item.get("id"), int)
        ]

    peak = max((score for _, score, _ in scored), default=0.0)
    if peak > 1.0:
        scored = [
            (item, score / peak, exact)
            for item, score, exact in scored
        ]
    return scored


def _search_once(
    scoring_keyword: str,
) -> list[tuple[dict[str, object], float, bool]]:
    query_keyword = _query_text(scoring_keyword) or scoring_keyword
    try:
        data = _post_search(query_keyword)
    except Exception:
        return []
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    scored = _score_items(items, scoring_keyword)
    peak = max((score for _, score, _ in scored), default=0.0)
    if peak < 0.5 and _MOVIE_WORDS_RE.search(scoring_keyword):
        retry_keyword = _strip_movie_words(query_keyword)
        if retry_keyword and retry_keyword != query_keyword:
            try:
                retry_data = _post_search(retry_keyword)
            except Exception:
                retry_data = None
            retry_items = (
                retry_data.get("data")
                if isinstance(retry_data, dict)
                else None
            )
            if isinstance(retry_items, list) and retry_items:
                retry_scored = _score_items(
                    retry_items, scoring_keyword
                )
                retry_peak = max(
                    (score for _, score, _ in retry_scored),
                    default=0.0,
                )
                if retry_peak > peak:
                    return retry_scored
    return scored


def search_bgm(keyword: str) -> list[dict[str, object]]:
    """Search Bangumi anime subjects for one 动画 value.

    Returns a list of dictionaries sorted by score (descending).  Each item
    has the fixed keys ``id``, ``name``, ``name_cn``, ``date``, ``score``,
    ``confidence`` and ``url``.  Failures and empty results return ``[]``.
    """
    keyword = _clean_keyword(keyword)
    if not keyword:
        return []
    keyword = _expand_abbreviation(keyword)

    ruled = _season_rules(keyword)
    if _ROMAN_RE.search(keyword) and ruled != keyword:
        variants = [keyword, ruled]
    else:
        variants = [ruled]

    merged: dict[int, tuple[dict[str, object], float, bool]] = {}
    for variant in variants:
        for item, score, exact in _search_once(variant):
            subject_id = item.get("id")
            if not isinstance(subject_id, int):
                continue
            current = merged.get(subject_id)
            if current is None:
                merged[subject_id] = (item, score, exact)
                continue
            _, old_score, old_exact = current
            if score > old_score or (
                score == old_score and exact and not old_exact
            ):
                merged[subject_id] = (item, score, exact)
    scored = list(merged.values())

    results: list[dict[str, object]] = []
    for item, score, exact in scored:
        if not exact:
            score = min(score, NON_EXACT_CAP)
        if score < ACCEPT_SCORE:
            continue
        subject_id = int(item["id"])
        name = str(item.get("name") or "")
        name_cn = str(item.get("name_cn") or "").strip() or name
        results.append(
            {
                "id": subject_id,
                "name": name,
                "name_cn": name_cn,
                "date": str(item.get("date") or ""),
                "score": round(score, 4),
                "confidence": _confidence(score, exact),
                "url": PROJECT_URL.format(subject_id=subject_id),
            }
        )

    results.sort(
        key=lambda row: (
            -float(row["score"]),
            str(row["date"]),
            int(row["id"]),
        )
    )
    return results


# 为偏好通用名称的调用方保留的向后兼容别名。
search_subjects = search_bgm

__all__ = ["search_bgm", "search_subjects"]
