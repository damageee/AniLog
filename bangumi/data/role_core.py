"""角色与声优值的共享解析。

本模块刻意不导入任何视图，使条目、角色和声优
页面都能依赖它而不产生循环导入。
"""

from __future__ import annotations

import re

_ROLE_PAREN = re.compile(r"^(.*?)[\(（]([^()（）]*)[\)）]\s*$")


def parse_roles(value: str) -> list[tuple[str, list[str]]]:
    """按换行拆分为 ``(name, cvs)`` 对，不再按空格拆分。"""
    roles: list[tuple[str, list[str]]] = []
    for line in str(value or "").splitlines():
        text = line.strip()
        if not text:
            continue
        match = _ROLE_PAREN.match(text)
        if match is not None:
            name = match.group(1).strip()
            cv_text = match.group(2)
        else:
            # 没有括号时整行作为角色名。
            name = text
            cv_text = ""

        cvs = [
            part.strip()
            for part in re.split(r"[/／]", cv_text)
            if part.strip()
        ]
        roles.append((name, cvs))
    return roles


def first_role_name(value: str) -> str:
    """返回首个非空行的角色名：去掉第一个括号及其后内容。"""
    for line in str(value or "").splitlines():
        text = line.strip()
        if not text:
            continue
        positions = [
            index
            for index in (text.find("("), text.find("（"))
            if index != -1
        ]
        if positions:
            text = text[: min(positions)]
        return text.strip()
    return ""


def role_lines(value: str) -> list[str]:
    """将每个角色格式化为 ``name(cv)`` 或仅 ``name``。"""
    lines: list[str] = []
    for name, cvs in parse_roles(value):
        if not name:
            continue
        lines.append(
            f"{name}({'/'.join(cvs)})" if cvs else name
        )
    return lines


def cast_names(value: str) -> list[str]:
    """返回一个角色单元格中所有不重复的声优名。"""
    seen: set[str] = set()
    names: list[str] = []
    for _, cvs in parse_roles(value):
        for cv in cvs:
            if cv and cv not in seen:
                seen.add(cv)
                names.append(cv)
    return names


def cast_roles(value: str, cast: str) -> list[str]:
    """返回一个单元格中 ``cast`` 扮演的所有不重复角色。"""
    roles: list[str] = []
    for name, cvs in parse_roles(value):
        if name and cast in cvs and name not in roles:
            roles.append(name)
    return roles
