"""应用帮助页。"""

from __future__ import annotations

import flet as ft

from bangumi.ui.theme import ui_text
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.views.navigation import (
    push_view,
)

HELP_PARAGRAPHS = (
    "初次上手，或是苦于回忆不起来看过什么？试试「随机」功能吧！（请尽量确保拥有优秀且科学的网络连接）",
    (
    "追加或编辑条目时在输入动画名后让输入框失焦后，应用会自动尝试在 Bangumi 上搜索相关动画，并提供列表供你选择后自动填充。",
    ),
    "「已追」页面里的骰子和 Bilibili 图标都是可以点击的，分别是随机和导入追番的功能。",
    "「追季」和里面的「前瞻」页面下长按空白处可显示每个季度内的数量。",
    "「追季」页面里具体季度里的具体条目按钮，以及「收藏」页面和子页面的条目按钮，悬浮或长按时都有额外操作选项。",
    "动画详情页里，长按分支的标题可直接编辑。单击/右击图片切换下/上一张，长按放大查看。",
    (
        "注：Bangumi 网站(bgm.tv)的访问需要特定的网络环境。以及部分功能（比如「随机」）建议开启代理后再使用。",
        "本应用大部分文字和组件在单击、双击、长按或拖动时都可能会有效果",
        "Esc可返回上一页，Shift+Esc返回首页。",
    ),
    "欢迎自行探索。",
)


def open_help(page: ft.Page) -> None:
    """将帮助视图压入当前视图栈。"""
    push_view(page, _build_help_view(page))


def _build_help_view(page: ft.Page) -> ft.View:
    controls: list[ft.Control] = []
    for item in HELP_PARAGRAPHS:
        if isinstance(item, tuple):
            for line in item:
                controls.append(ui_text(line, size=18))
        if isinstance(item, str):
            controls.append(ui_text(item, size=18))
        controls.append(ft.Container(height=16))
    view = ft.View(
        route="/help",
        appbar=ft.AppBar(title=ui_text("应用使用说明")),
        padding=page_padding(),
        controls=[vertical_page(controls, spacing=4)],
    )
    view.data = {
        "rebuild": lambda: _build_help_view(page)
    }
    return view
