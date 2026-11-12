"""角色与声优值的共享解析。

本模块刻意不导入任何视图，使条目、角色和声优
页面都能依赖它而不产生循环导入。
"""

from __future__ import annotations


def parse_roles(value: str) -> list[tuple[str, list[str]]]:
    """将一个单元格拆成 ``(name, cvs)`` 对。"""
    roles: list[tuple[str, list[str]]] = []
    for token in str(value or "").split():
        opening = token.find("(")
        if opening != -1 and token.endswith(")"):
            name = token[:opening].strip()
            cv_text = token[opening + 1 : -1]
        else:
            name = token
            cv_text = ""

        cvs = [
            part.strip()
            for part in cv_text.split("/")
            if part.strip()
        ]
        roles.append((name, cvs))
    return roles


def first_role_name(value: str) -> str:
    """仅返回第一个角色名，不含声优列表。"""
    for name, _ in parse_roles(value):
        if name:
            return name
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
