"""条目表单页：布局、封面、校验与保存回调。

表单本身从不接触存储。提供回调时，持久化由回调负责；
页面会压入当前视图栈顶部，使观影页保留其滚动/搜索状态。
"""

from __future__ import annotations

import asyncio
import calendar
import datetime as dt
from dataclasses import dataclass, field
from typing import Callable

import flet as ft
from bangumi.core.utils import to_bgm_id

from bangumi.core.cover_proc import invalidate_cover
from bangumi.services.bgm_characters import get_characters
from bangumi.services.bgm_info import get_subject_info
from bangumi.services.bgm_persons import get_persons
from bangumi.services.bgm_pic import (
    cover_path,
    has_cover,
    save_subject_image,
)
from bangumi.services.bgm_search import search_bgm
from bangumi.io.importer import (
    _date_text,
    _normalize_broadcast,
    _normalize_completion,
    _parse_date,
)
from bangumi.data.preferences import Preferences
from bangumi.data.dates import format_iso_date
from bangumi.ui.theme import ui_text, ui_text_style
from bangumi.ui.colors import (
    background_color,
    foreground_color,
)
from bangumi.ui.feedback import (
    confirmation_dialog,
    show_error_dialog,
)
from bangumi.ui.interaction import (
    hover_icon,
    is_attached,
)
from bangumi.ui.layout import (
    page_padding,
    vertical_page,
)
from bangumi.ui.text_metrics import text_width
from bangumi.views.navigation import (
    push_view,
)
from bangumi.data.role_core import parse_roles
from bangumi.views.widgets.image_preview import show_image_preview
from bangumi.views.widgets.toast import show_toast
from bangumi.data.watched_data import (
    RECORD_FIELDS,
    STUDIO_SEPARATOR,
    Record,
    load_records,
    normalize_staff,
    split_studios,
    split_tags,
)

ENTRY_FORM_ROUTE = "/watched/entry/new"


CHOOSE_DATE = "选择日期"
CHOOSE_CATEGORY = "选择类型"
HINT_ENTRY = "原作/动画名称"
HINT_ANIME = "动画名称"
HINT_STAFF_KEY = "职务（如 导演/原作）"
HINT_STAFF_VALUE = "姓名"
HINT_STUDIO = "制作公司"
HINT_SPEC = "动画长度"
HINT_RATING = "0~100"
HINT_TAG = "标签"
HINT_ROLE = "角色（越靠前越重要）"
HINT_CV = "声优"
HINT_REMARK = (
    "你小子给我听好了，青子可不是“喜欢”这个词可以形容的。"
    "对我来说就是空气，就是氧气，就是水分，就是光明，就是老婆。"
    "没有她我就会死的。"
)
WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]
CALENDAR_YEAR_PAGE = 12
FORM_COLUMNS = {"xs": 12, "sm": 12, "md": 10, "lg": 7, "xl": 5}
FIELD_SPACING = 18
ROW_SPACING = 8
INPUT_HEIGHT = 46
CATEGORY_OPTIONS = [
    "小说改",
    "漫画改",
    "游戏改",
    "原创",
    "电影",
    "跨媒体",
    "音乐衍生",
    "其他",
]
SPEC_PRESETS = ["12话", "24话", "SP", "OVA", "OAD", "90分钟"]
BROADCAST_POINT = "point"
BROADCAST_RANGE = "range"


def format_date(value: dt.date | None) -> str:
    """Format a date as ``YYYY年M月D日``."""
    return format_iso_date(value, choose=CHOOSE_DATE)


def _clamp_score_text(value: str) -> str:
    """将评分限制在 0..100；空白和文本保持不变。"""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number < 0:
        return "0"
    if number > 100:
        return "100"
    return text


def _alpha(color: str, opacity: float, fallback: str) -> str:
    try:
        return ft.Colors.with_opacity(opacity, color)
    except Exception:
        return fallback


def _fetch_bgm_info(
    subject_id: int,
    original_name: str,
    fixed: set[str],
) -> dict[str, object]:
    """仅合并表单实际会用到的接口数据。"""
    info = get_subject_info(subject_id, original_name)
    if str(info.get("error") or "").strip():
        return info
    if not ("staff" in fixed and "studio" in fixed):
        info = {**info, **get_persons(subject_id)}
    if "role" not in fixed:
        info = {**info, **get_characters(subject_id)}
    return info


@dataclass
class BroadcastItem:
    """One 放送 row: either a single date point or a start/end range."""

    kind: str = "point"
    point: dt.date | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    initialized: bool = False
    point_label: ft.Text | None = None
    start_label: ft.Text | None = None
    end_label: ft.Text | None = None
    slot: ft.Container = field(default_factory=ft.Container)


class EntryForm:
    """构建并持有条目表单控件。"""

    def __init__(
        self,
        page: ft.Page,
        *,
        record: Record | None = None,
        on_save: Callable[[Record], None] | None = None,
        on_delete: Callable[[], None] | None = None,
    ) -> None:
        self.page = page
        self.original_record = record
        self.preferences = Preferences.load()
        self.bgm_id = -1
        self._pending_cover_delete: int | None = None
        self.on_save = on_save
        self.on_delete = on_delete
        self.dark = page.theme_mode == ft.ThemeMode.DARK
        self.foreground = foreground_color(page)
        grey = ft.Colors.GREY_400 if self.dark else ft.Colors.GREY_600
        self.secondary = _alpha(self.foreground, 0.65, grey)
        self.border = _alpha(
            self.foreground,
            0.25,
            ft.Colors.GREY_600 if self.dark else ft.Colors.GREY_400,
        )
        base = ft.Colors.WHITE if self.dark else ft.Colors.BLACK
        self.input_bg = _alpha(
            base,
            0.06 if self.dark else 0.03,
            "#1E1E1E" if self.dark else "#F5F5F5",
        )
        self.panel_bg = _alpha(
            base,
            0.05 if self.dark else 0.03,
            "#1E1E1E" if self.dark else "#F5F5F5",
        )

        # 内联日历状态：同一时间只打开一个面板。
        self.calendar_slot: ft.Container | None = None
        self.calendar_apply: Callable[[dt.date | None], None] | None = None
        self.calendar_selected: dt.date | None = None
        today = dt.date.today()
        self.calendar_year = today.year
        self.calendar_month = today.month
        self.calendar_mode = "year"

        # 校验状态：每个待校验字段对应一个隐藏错误标签。
        self.error_labels: dict[str, ft.Text] = {}

        # 纯文本字段。
        self.entry_field = self._text_field(hint_text=HINT_ENTRY)
        self.anime_field = self._text_field(hint_text=HINT_ANIME)
        self.former_name = ""
        self.former_name_label = ui_text(
            "",
            size=12,
            color=self.secondary,
            visible=False,
        )
        self.former_name_container = ft.Container(
            content=self.former_name_label,
            visible=False,
            tooltip="点击把曾用名填回动画字段",
            on_click=self._apply_former_name,
        )
        self.bgm_results = ft.Column(
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.bgm_choices: dict[int, dict] = {}
        self.selected_bgm_id: int | None = None
        self._bgm_token = 0
        self._bgm_detail_token = 0
        self._bgm_loading: ft.Container | None = None
        self._anime_dirty = False
        self._suppress_anime_change = False
        self._anime_previous = ""
        self._entry_auto = False
        self.anime_field.on_change = self._on_anime_change
        self.entry_field.on_change = self._on_entry_change
        self.anime_field.on_blur = self._commit_anime_search
        self.anime_field.on_submit = (
            lambda event: self._commit_anime_search(event, force=True)
        )
        self.score_field = self._text_field(hint_text=HINT_RATING)
        self.score_field.input_filter = ft.NumbersOnlyInputFilter()
        self.score_field.on_change = self._clamp_score
        self.score_field.on_blur = self._clamp_score
        self.remark_field = self._text_field(
            hint_text=HINT_REMARK,
            multiline=True,
        )

        # 类型: a button that shows the picked option.
        self.category_value = ""
        self.category_label = ui_text(
            CHOOSE_CATEGORY, size=13, color=self.foreground
        )
        self.category_button = self._build_category_button()

        # 规格: one editable field with preset buttons below.
        self.spec_field = self._text_field(hint_text=HINT_SPEC)
        self.spec_block = ft.Column(
            spacing=ROW_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                self.spec_field,
                ft.Row(
                    wrap=True,
                    spacing=ROW_SPACING,
                    run_spacing=ROW_SPACING,
                    controls=[
                        self._spec_preset_button(label)
                        for label in SPEC_PRESETS
                    ],
                ),
            ],
        )

        # 单值列表。
        self.tag_fields: list[ft.TextField] = [
            self._text_field(hint_text=HINT_TAG)
        ]
        self.tag_column = ft.Column(spacing=ROW_SPACING)
        self._rebuild_text_list(
            self.tag_fields, self.tag_column, self._add_tag
        )
        self.studio_fields: list[ft.TextField] = [
            self._text_field(hint_text=HINT_STUDIO)
        ]
        self.studio_column = ft.Column(spacing=ROW_SPACING)
        self._rebuild_text_list(
            self.studio_fields, self.studio_column, self._add_studio
        )

        # STAFF: (职务, 姓名) pairs.
        self.staff_pairs: list[tuple[ft.TextField, ft.TextField]] = [
            self._new_staff_pair()
        ]
        self.staff_column = ft.Column(spacing=ROW_SPACING)
        self._rebuild_staff()

        # 角色: (角色名, 声优) pairs.
        self.role_pairs: list[tuple[ft.TextField, ft.TextField]] = [
            (
                self._text_field(hint_text=HINT_ROLE),
                self._text_field(hint_text=HINT_CV),
            )
        ]
        self.role_column = ft.Column(spacing=ROW_SPACING)
        self._rebuild_role()

        # 放送: point rows and one range row are kept separately.
        self.broadcast_mode = BROADCAST_POINT
        self.point_items: list[BroadcastItem] = [
            BroadcastItem(kind=BROADCAST_POINT)
        ]
        self.range_item = BroadcastItem(kind=BROADCAST_RANGE)
        self.broadcast_column = ft.Column(spacing=ROW_SPACING)
        self._rebuild_broadcast()

        # 补完: single date button with the same inline calendar.
        self.completion_date: dt.date | None = None
        self.completion_label = ui_text(
            format_date(None), size=13, color=self.foreground
        )
        self.completion_slot = ft.Container(visible=False)
        self.completion_button = self._date_button(
            self.completion_label, self._open_completion
        )
        self.completion_block = ft.Column(
            spacing=6,
            controls=[
                ft.Row(spacing=ROW_SPACING, controls=[self.completion_button]),
                self.completion_slot,
            ],
        )

        # 续: public sequel flag.
        self.sequel_checkbox = ft.Checkbox(
            label=ui_text("有公开续作"),
            value=False,
        )
        self.skip_fill_checkbox = ft.Checkbox(
            label=ui_text("不自动导入"),
            value=False,
        )

        if record is not None:
            self._apply_record(record)

        self.card = self._build_card()

    # ------------------------------------------------------------------
    # 从现有记录预填
    # ------------------------------------------------------------------

    def _clamp_score(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        current = str(self.score_field.value or "")
        clamped = _clamp_score_text(current)
        if clamped != current:
            self.score_field.value = clamped
            self.score_field.update()

    def _apply_record(self, record: Record) -> None:
        self.bgm_id = to_bgm_id(record.get("bgm_id"))
        self._pending_cover_delete = None
        entry = str(record.get("entry") or record.get("anime") or "")
        self.entry_field.value = entry
        self.anime_field.value = str(record.get("anime") or "")
        self._anime_previous = (
            str(record.get("anime") or "").strip()
        )
        self._entry_auto = False
        self.former_name = str(record.get("former_name") or "")
        self._refresh_former_name_label()
        staff = normalize_staff(record.get("staff"))
        self.staff_pairs = []
        for key, value in staff.items():
            key_field, value_field = self._new_staff_pair()
            key_field.value = key
            value_field.value = value
            self.staff_pairs.append((key_field, value_field))
        if not self.staff_pairs:
            self.staff_pairs = [self._new_staff_pair()]
        self._rebuild_staff()
        self.spec_field.value = str(record.get("specification") or "")
        self.score_field.value = _clamp_score_text(
            str(record.get("rating") or "")
        )
        self.remark_field.value = str(record.get("remark") or "")

        category = str(record.get("category") or "").strip()
        if category:
            self.category_value = category
            self.category_label.value = category

        self.sequel_checkbox.value = bool(record.get("sequel"))
        self.skip_fill_checkbox.value = bool(record.get("skip_fill"))

        tags = split_tags(str(record.get("tag") or ""))
        self.tag_fields = [
            self._text_field(hint_text=HINT_TAG)
            for _ in range(max(1, len(tags)))
        ]
        for text_field, value in zip(self.tag_fields, tags):
            text_field.value = value
        self._rebuild_text_list(
            self.tag_fields, self.tag_column, self._add_tag
        )

        studios = split_studios(str(record.get("studio") or ""))
        self.studio_fields = [
            self._text_field(hint_text=HINT_STUDIO)
            for _ in range(max(1, len(studios)))
        ]
        for text_field, value in zip(self.studio_fields, studios):
            text_field.value = value
        self._rebuild_text_list(
            self.studio_fields, self.studio_column, self._add_studio
        )

        pairs = parse_roles(str(record.get("role") or ""))
        self.role_pairs = []
        for name, cvs in pairs:
            name_field = self._text_field(hint_text=HINT_ROLE)
            cv_field = self._text_field(hint_text=HINT_CV)
            name_field.value = name
            cv_field.value = "/".join(cvs) if cvs else "无"
            self.role_pairs.append((name_field, cv_field))
        if not self.role_pairs:
            self.role_pairs = [
                (
                    self._text_field(hint_text=HINT_ROLE),
                    self._text_field(hint_text=HINT_CV),
                )
            ]
        self._rebuild_role()

        self._apply_broadcast(str(record.get("broadcast") or ""))

        completion = _parse_date(
            _normalize_completion(str(record.get("completion") or ""))
        )
        if completion is not None:
            self.completion_date = completion
            self.completion_label.value = format_date(completion)

        self._refresh_cover_buttons()

    def _apply_broadcast(self, value: str) -> None:
        normalized = _normalize_broadcast(value)
        if "~" in normalized:
            start_text, end_text = normalized.split("~", 1)
            start = _parse_date(start_text)
            end = _parse_date(end_text)
            if start is not None and end is not None:
                self.range_item = BroadcastItem(
                    kind=BROADCAST_RANGE,
                    start=start,
                    end=end,
                    initialized=True,
                )
                self.broadcast_mode = BROADCAST_RANGE
                self._rebuild_broadcast()
                return

        dates = [
            _parse_date(token)
            for token in normalized.split(" ")
            if token
        ]
        points = [
            BroadcastItem(kind=BROADCAST_POINT, point=date)
            for date in dates
            if date is not None
        ]
        self.point_items = points or [BroadcastItem(kind=BROADCAST_POINT)]
        self.broadcast_mode = BROADCAST_POINT
        self._rebuild_broadcast()

    # ------------------------------------------------------------------
    # 文本字段与标签
    # ------------------------------------------------------------------

    def _text_field(
        self,
        *,
        hint_text: str = "",
        multiline: bool = False,
    ) -> ft.TextField:
        return ft.TextField(
            hint_text=hint_text,
            hint_style=ui_text_style(color=self.secondary, size=13),
            text_style=ui_text_style(color=self.foreground, size=14),
            bgcolor=self.input_bg,
            border_color=self.border,
            focused_border_color=ft.Colors.BLUE,
            border_radius=8,
            border=ft.OutlineInputBorder(border_radius=8),
            content_padding=ft.Padding.symmetric(
                horizontal=12, vertical=12 if multiline else 10
            ),
            dense=True,
            multiline=multiline,
            min_lines=3 if multiline else 1,
            max_lines=3 if multiline else 1,
            height=None if multiline else INPUT_HEIGHT,
        )

    def _label(self, text: str) -> ft.Text:
        return ui_text(
            text,
            size=14,
            weight=ft.FontWeight.BOLD,
            color=self.foreground,
        )

    def _field(
        self,
        label: str,
        control: ft.Control,
        *,
        key: str | None = None,
    ) -> ft.Column:
        header: list[ft.Control] = [self._label(label)]
        if key is not None:
            error = ui_text("", size=12, color=ft.Colors.RED, visible=False)
            self.error_labels[key] = error
            header.append(error)
        return ft.Column(
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=header,
                ),
                control,
            ],
        )

    def _add_icon(self, handler: Callable) -> ft.Control:
        return hover_icon(
            self.page,
            ft.Icons.ADD_CIRCLE_OUTLINE,
            size=20,
            color=ft.Colors.BLUE,
            tooltip="新增一行",
            on_click=handler,
        )

    def _remove_icon(self, handler: Callable) -> ft.Control:
        return hover_icon(
            self.page,
            ft.Icons.REMOVE_CIRCLE_OUTLINE,
            size=20,
            color=self.secondary,
            tooltip="删除一行",
            on_click=handler,
        )

    # ------------------------------------------------------------------
    # 类型 and 规格
    # ------------------------------------------------------------------

    def _build_category_button(self) -> ft.PopupMenuButton:
        return ft.PopupMenuButton(
            content=ft.Container(
                bgcolor=self.input_bg,
                border=ft.Border.all(1, self.border),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                content=ft.Row(
                    spacing=6,
                    controls=[
                        self.category_label,
                        ft.Icon(
                            ft.Icons.ARROW_DROP_DOWN,
                            size=18,
                            color=self.secondary,
                        ),
                    ],
                ),
            ),
            items=[
                ft.PopupMenuItem(
                    content=ui_text(option, size=13, color=self.foreground),
                    on_click=lambda event, v=option: self._select_category(
                        v
                    ),
                )
                for option in CATEGORY_OPTIONS
            ],
        )

    def _select_category(self, value: str) -> None:
        self.category_value = value
        self.category_label.value = value
        self.category_label.update()

    def _spec_preset_button(self, label: str) -> ft.OutlinedButton:
        return ft.OutlinedButton(
            content=ui_text(label, size=12, color=self.foreground),
            on_click=lambda event, v=label: self._apply_spec_preset(v),
            style=ft.ButtonStyle(
                color=self.foreground,
                side=ft.BorderSide(1, self.border),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            ),
        )

    def _apply_spec_preset(self, label: str) -> None:
        self.spec_field.value = label
        self.spec_field.update()

    # ------------------------------------------------------------------
    # Single value lists (TAG / 制作公司)
    # ------------------------------------------------------------------

    def _rebuild_text_list(
        self,
        fields: list[ft.TextField],
        column: ft.Column,
        add_handler: Callable,
    ) -> None:
        rows: list[ft.Control] = []
        last_index = len(fields) - 1
        for index, text_field in enumerate(fields):
            text_field.expand = True
            controls: list[ft.Control] = [
                text_field,
                self._remove_icon(
                    lambda event,
                    i=index,
                    f=fields,
                    c=column,
                    a=add_handler: self._remove_text(f, c, a, i)
                ),
            ]
            if index == last_index:
                controls.append(self._add_icon(add_handler))
                if column is self.tag_column:
                    controls.append(self._tag_picker(text_field))
            rows.append(
                ft.Row(
                    spacing=ROW_SPACING,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=controls,
                )
            )
        column.controls = rows

    def _tag_picker(self, field: ft.TextField) -> ft.Control:
        counts: dict[str, int] = {}
        for record in load_records():
            for tag in split_tags(record.get("tag")):
                counts[tag] = counts.get(tag, 0) + 1
        tags = [
            tag
            for tag in sorted(
                counts,
                key=lambda name: (-counts[name], name),
            )
        ]
        if not tags:
            tags = sorted(Preferences.load().tag_colors)
        return ft.PopupMenuButton(
            icon=ft.Icons.TAG,
            tooltip="选择已有 TAG",
            disabled=not tags,
            items=[
                ft.PopupMenuItem(
                    content=ui_text(tag),
                    on_click=(
                        lambda event, t=tag: self._fill_tag(field, t)
                    ),
                )
                for tag in tags
            ],
        )

    def _fill_tag(self, field: ft.TextField, tag: str) -> None:
        field.value = tag
        try:
            field.update()
        except Exception:
            pass

    def _add_text(
        self,
        fields: list[ft.TextField],
        column: ft.Column,
        add_handler: Callable,
        hint_text: str,
        event: ft.ControlEvent | None = None,
    ) -> None:
        fields.append(self._text_field(hint_text=hint_text))
        self._rebuild_text_list(fields, column, add_handler)
        column.update()

    def _remove_text(
        self,
        fields: list[ft.TextField],
        column: ft.Column,
        add_handler: Callable,
        index: int,
    ) -> None:
        if len(fields) > 1:
            fields.pop(index)
        else:
            fields[0].value = ""
        self._rebuild_text_list(fields, column, add_handler)
        column.update()

    def _add_tag(self, event: ft.ControlEvent | None = None) -> None:
        self._add_text(
            self.tag_fields,
            self.tag_column,
            self._add_tag,
            HINT_TAG,
            event,
        )

    def _add_studio(self, event: ft.ControlEvent | None = None) -> None:
        self._add_text(
            self.studio_fields,
            self.studio_column,
            self._add_studio,
            HINT_STUDIO,
            event,
        )

    # ------------------------------------------------------------------
    # 角色 pairs
    # ------------------------------------------------------------------

    def _rebuild_role(self) -> None:
        rows: list[ft.Control] = []
        last_index = len(self.role_pairs) - 1
        for index, (name_field, cv_field) in enumerate(
            self.role_pairs
        ):
            name_field.expand = True
            cv_field.expand = True
            controls: list[ft.Control] = [
                name_field,
                cv_field,
                self._remove_icon(
                    lambda event, i=index: self._remove_role(i)
                ),
            ]
            if index == last_index:
                controls.append(self._add_icon(self._add_role))
            rows.append(
                ft.Row(
                    spacing=ROW_SPACING,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=controls,
                )
            )
        self.role_column.controls = rows

    def _add_role(
        self, event: ft.ControlEvent | None = None
    ) -> None:
        self.role_pairs.append(
            (
                self._text_field(hint_text=HINT_ROLE),
                self._text_field(hint_text=HINT_CV),
            )
        )
        self._rebuild_role()
        self.role_column.update()

    def _remove_role(self, index: int) -> None:
        if len(self.role_pairs) > 1:
            self.role_pairs.pop(index)
        else:
            name_field, cv_field = self.role_pairs[0]
            name_field.value = ""
            cv_field.value = ""
        self._rebuild_role()
        self.role_column.update()

    # ------------------------------------------------------------------
    # STAFF pairs
    # ------------------------------------------------------------------

    def _new_staff_pair(
        self,
    ) -> tuple[ft.TextField, ft.TextField]:
        return (
            self._text_field(hint_text=HINT_STAFF_KEY),
            self._text_field(hint_text=HINT_STAFF_VALUE),
        )

    def _rebuild_staff(self) -> None:
        rows: list[ft.Control] = []
        last_index = len(self.staff_pairs) - 1
        for index, (key_field, value_field) in enumerate(
            self.staff_pairs
        ):
            key_field.expand = True
            value_field.expand = True
            controls: list[ft.Control] = [
                key_field,
                value_field,
                self._remove_icon(
                    lambda event, i=index: self._remove_staff(i)
                ),
            ]
            if index == last_index:
                controls.append(self._add_icon(self._add_staff))
            rows.append(
                ft.Row(
                    spacing=ROW_SPACING,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=controls,
                )
            )
        self.staff_column.controls = rows

    def _add_staff(
        self, event: ft.ControlEvent | None = None
    ) -> None:
        self.staff_pairs.append(self._new_staff_pair())
        self._rebuild_staff()
        self.staff_column.update()

    def _remove_staff(self, index: int) -> None:
        if len(self.staff_pairs) > 1:
            self.staff_pairs.pop(index)
        else:
            key_field, value_field = self.staff_pairs[0]
            key_field.value = ""
            value_field.value = ""
        self._rebuild_staff()
        self.staff_column.update()

    def _reset_staff_pairs(self) -> None:
        self.staff_pairs = [self._new_staff_pair()]
        self._rebuild_staff()

    # ------------------------------------------------------------------
    # 放送 rows (point / range)
    # ------------------------------------------------------------------

    def _date_button(
        self,
        label: ft.Text,
        handler: Callable,
    ) -> ft.OutlinedButton:
        return ft.OutlinedButton(
            expand=True,
            on_click=handler,
            style=ft.ButtonStyle(
                color=self.foreground,
                side=ft.BorderSide(1, self.border),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=12),
            ),
            content=ft.Row(
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        ft.Icons.CALENDAR_MONTH_OUTLINED,
                        size=16,
                        color=self.secondary,
                    ),
                    label,
                ],
            ),
        )

    def _broadcast_mode_row(self) -> ft.Row:
        return ft.Row(
            spacing=ROW_SPACING,
            controls=[
                self._mode_button("时间点", BROADCAST_POINT),
                self._mode_button("时间段", BROADCAST_RANGE),
            ],
        )

    def _mode_button(self, label: str, mode: str) -> ft.Control:
        if self.broadcast_mode == mode:
            return ft.Button(
                content=ui_text(label, size=13, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.BLUE,
                on_click=lambda event, m=mode: self._switch_mode(m),
            )
        return ft.OutlinedButton(
            content=ui_text(label, size=13, color=self.foreground),
            on_click=lambda event, m=mode: self._switch_mode(m),
            style=ft.ButtonStyle(
                color=self.foreground,
                side=ft.BorderSide(1, self.border),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            ),
        )

    def _switch_mode(self, mode: str) -> None:
        if mode == self.broadcast_mode:
            return
        self.broadcast_mode = mode
        self._rebuild_broadcast()
        self.broadcast_column.update()

    def _rebuild_broadcast(self) -> None:
        self._close_calendar()
        controls: list[ft.Control] = [self._broadcast_mode_row()]
        if self.broadcast_mode == BROADCAST_POINT:
            last_index = len(self.point_items) - 1
            for index, item in enumerate(self.point_items):
                item.slot = ft.Container(visible=False)
                controls.append(
                    ft.Column(
                        spacing=6,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            self._point_row(
                                index, item, is_last=index == last_index
                            ),
                            item.slot,
                        ],
                    )
                )
        else:
            item = self.range_item
            item.slot = ft.Container(visible=False)
            controls.append(
                ft.Column(
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[self._range_row(item), item.slot],
                )
            )
        self.broadcast_column.controls = controls

    def _point_row(
        self, index: int, item: BroadcastItem, *, is_last: bool
    ) -> ft.Row:
        item.point_label = ui_text(
            format_date(item.point), size=13, color=self.foreground
        )
        controls: list[ft.Control] = [
            self._date_button(
                item.point_label,
                lambda event, i=index: self._open_point(i),
            ),
            self._remove_icon(
                lambda event, i=index: self._remove_point(i)
            ),
        ]
        if is_last:
            controls.append(self._add_icon(self._add_point))
        return ft.Row(
            spacing=ROW_SPACING,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=controls,
        )

    def _range_row(self, item: BroadcastItem) -> ft.Row:
        item.start_label = ui_text(
            format_date(item.start), size=13, color=self.foreground
        )
        item.end_label = ui_text(
            format_date(item.end), size=13, color=self.foreground
        )
        return ft.Row(
            spacing=ROW_SPACING,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self._date_button(
                    item.start_label,
                    lambda event: self._open_range("start"),
                ),
                ui_text("~", size=13, color=self.secondary),
                self._date_button(
                    item.end_label,
                    lambda event: self._open_range("end"),
                ),
            ],
        )

    def _add_point(self, event: ft.ControlEvent | None = None) -> None:
        self.point_items.append(BroadcastItem(kind=BROADCAST_POINT))
        self._rebuild_broadcast()
        self.broadcast_column.update()

    def _remove_point(self, index: int) -> None:
        self._close_calendar()
        if len(self.point_items) > 1:
            self.point_items.pop(index)
        else:
            self.point_items[0].point = None
        self._rebuild_broadcast()
        self.broadcast_column.update()

    def _open_point(self, index: int) -> None:
        item = self.point_items[index]

        def apply(value: dt.date | None) -> None:
            item.point = value
            if item.point_label is not None:
                item.point_label.value = format_date(value)

        self._open_calendar(item.slot, item.point, apply)

    def _open_range(self, side: str) -> None:
        item = self.range_item
        current = item.start if side == "start" else item.end

        def apply(value: dt.date | None) -> None:
            if value is not None and not item.initialized:
                item.start = value
                item.end = value
                item.initialized = True
            elif side == "start":
                item.start = value
            else:
                item.end = value

            if (
                item.start is not None
                and item.end is not None
                and item.start > item.end
            ):
                item.start, item.end = item.end, item.start

            if item.start_label is not None:
                item.start_label.value = format_date(item.start)
            if item.end_label is not None:
                item.end_label.value = format_date(item.end)

        self._open_calendar(item.slot, current, apply)

    # ------------------------------------------------------------------
    # 补完 single date
    # ------------------------------------------------------------------

    def _open_completion(self, event: ft.ControlEvent | None = None) -> None:
        def apply(value: dt.date | None) -> None:
            self.completion_date = value
            self.completion_label.value = format_date(value)

        self._open_calendar(
            self.completion_slot, self.completion_date, apply
        )

    # ------------------------------------------------------------------
    # 内联日历
    # ------------------------------------------------------------------

    def _open_calendar(
        self,
        slot: ft.Container,
        current: dt.date | None,
        apply: Callable[[dt.date | None], None],
    ) -> None:
        previous = self.calendar_slot
        if previous is not None and previous is not slot:
            previous.content = None
            previous.visible = False

        self.calendar_slot = slot
        self.calendar_apply = apply
        self.calendar_selected = current
        base = current or dt.date.today()
        self.calendar_year = base.year
        self.calendar_month = base.month
        self.calendar_mode = "year"

        slot.content = self._calendar_panel()
        slot.visible = True
        if previous is not None and previous is not slot:
            self.page.update(previous, slot)
        else:
            slot.update()

    def _close_calendar(self) -> None:
        if self.calendar_slot is not None:
            self.calendar_slot.content = None
            self.calendar_slot.visible = False
        self.calendar_slot = None
        self.calendar_apply = None

    def _render_calendar(self) -> None:
        if self.calendar_slot is None:
            return
        self.calendar_slot.content = self._calendar_panel()
        self.calendar_slot.update()

    def _calendar_panel(self) -> ft.Container:
        if self.calendar_mode == "year":
            return self._year_panel()
        return self._month_panel()

    def _month_panel(self) -> ft.Container:
        today = dt.date.today()
        header = ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                hover_icon(
                    self.page,
                    ft.Icons.CHEVRON_LEFT,
                    size=18,
                    color=self.foreground,
                    tooltip="上个月",
                    on_click=self._previous_month,
                    padding=4,
                ),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    on_click=self._show_year_view,
                    tooltip="选择年份",
                    content=ui_text(
                        f"{self.calendar_year}年{self.calendar_month}月",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=self.foreground,
                    ),
                ),
                hover_icon(
                    self.page,
                    ft.Icons.CHEVRON_RIGHT,
                    size=18,
                    color=self.foreground,
                    tooltip="下个月",
                    on_click=self._next_month,
                    padding=4,
                ),
            ],
        )

        weekdays = ft.Row(
            spacing=0,
            controls=[
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        label, size=11, color=self.secondary
                    ),
                )
                for label in WEEKDAY_LABELS
            ],
        )

        weeks = calendar.monthcalendar(
            self.calendar_year, self.calendar_month
        )
        weeks = weeks + [[0] * 7] * (6 - len(weeks))
        grid = [
            ft.Row(
                spacing=0,
                controls=[self._day_cell(day, today) for day in week],
            )
            for week in weeks[:6]
        ]

        footer = self._calendar_footer()

        return ft.Container(
            bgcolor=self.panel_bg,
            border=ft.Border.all(1, self.border),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            content=ft.Column(
                spacing=2,
                controls=[header, weekdays, *grid, footer],
            ),
        )

    def _calendar_footer(self) -> ft.Row:
        return ft.Row(
            spacing=0,
            alignment=ft.MainAxisAlignment.END,
            controls=[
                ft.TextButton(
                    content=ui_text("今天", size=12, color=self.foreground),
                    on_click=self._select_today,
                ),
                ft.TextButton(
                    content=ui_text("清空", size=12, color=self.foreground),
                    on_click=self._clear_calendar_date,
                ),
                ft.TextButton(
                    content=ui_text("确定", size=12, color=ft.Colors.BLUE),
                    on_click=self._confirm_calendar_date,
                ),
            ],
        )

    def _calendar_year_bounds(self) -> tuple[int, int]:
        today = dt.date.today()
        years = [2000, today.year, today.year + 5, self.calendar_year]
        if self.calendar_selected is not None:
            years.append(self.calendar_selected.year)
        return min(years), max(years)

    def _year_page_start(self) -> int:
        low, _ = self._calendar_year_bounds()
        offset = max(0, self.calendar_year - low)
        return low + (offset // CALENDAR_YEAR_PAGE) * CALENDAR_YEAR_PAGE

    def _year_panel(self) -> ft.Container:
        today = dt.date.today()
        low, high = self._calendar_year_bounds()
        start = self._year_page_start()
        end = min(high, start + CALENDAR_YEAR_PAGE - 1)
        years = list(range(start, end + 1))

        rows: list[ft.Control] = []
        for index in range(0, len(years), 3):
            cells: list[ft.Control] = [
                self._year_cell(year, today)
                for year in years[index:index + 3]
            ]
            while len(cells) < 3:
                cells.append(ft.Container(expand=1, height=30))
            rows.append(ft.Row(spacing=0, controls=cells))

        header = ft.Row(
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                hover_icon(
                    self.page,
                    ft.Icons.CHEVRON_LEFT,
                    size=18,
                    color=self.foreground,
                    tooltip="往前",
                    on_click=self._previous_year_page,
                    disabled=start <= low,
                    padding=4,
                ),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ui_text(
                        "选择年份",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=self.foreground,
                    ),
                ),
                hover_icon(
                    self.page,
                    ft.Icons.CHEVRON_RIGHT,
                    size=18,
                    color=self.foreground,
                    tooltip="往后",
                    on_click=self._next_year_page,
                    disabled=start + CALENDAR_YEAR_PAGE > high,
                    padding=4,
                ),
            ],
        )

        return ft.Container(
            bgcolor=self.panel_bg,
            border=ft.Border.all(1, self.border),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            content=ft.Column(
                spacing=2,
                controls=[header, *rows, self._calendar_footer()],
            ),
        )

    def _year_cell(self, year: int, today: dt.date) -> ft.Control:
        selected = (
            self.calendar_selected is not None
            and self.calendar_selected.year == year
        )
        current = year == today.year
        return ft.Container(
            expand=1,
            height=30,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.BLUE if selected else None,
            border=(
                ft.Border.all(1, ft.Colors.BLUE)
                if current and not selected
                else None
            ),
            on_click=lambda event, y=year: self._pick_year(y),
            content=ui_text(
                str(year),
                size=12,
                color=ft.Colors.WHITE if selected else self.foreground,
            ),
        )

    def _pick_year(self, year: int) -> None:
        today = dt.date.today()
        self.calendar_year = year
        if (
            self.calendar_selected is not None
            and self.calendar_selected.year == year
        ):
            self.calendar_month = self.calendar_selected.month
        elif year == today.year:
            self.calendar_month = today.month
        else:
            self.calendar_month = 1
        self.calendar_mode = "month"
        self._render_calendar()

    def _show_year_view(self, event: ft.ControlEvent) -> None:
        if self.calendar_slot is None:
            return
        self.calendar_mode = "year"
        self._render_calendar()

    def _previous_year_page(self, event: ft.ControlEvent) -> None:
        self._shift_year_page(-1)

    def _next_year_page(self, event: ft.ControlEvent) -> None:
        self._shift_year_page(1)

    def _shift_year_page(self, delta: int) -> None:
        low, high = self._calendar_year_bounds()
        start = self._year_page_start() + delta * CALENDAR_YEAR_PAGE
        start = max(low, min(start, high))
        self.calendar_year = start
        self._render_calendar()

    def _day_cell(
        self, day: int, today: dt.date
    ) -> ft.Control:
        if not day:
            return ft.Container(expand=1, height=30)

        value = dt.date(self.calendar_year, self.calendar_month, day)
        selected = self.calendar_selected == value
        return ft.Container(
            expand=1,
            height=30,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.BLUE if selected else None,
            border=(
                ft.Border.all(1, ft.Colors.BLUE)
                if value == today and not selected
                else None
            ),
            on_click=lambda event, v=value: self._pick_day(v),
            content=ui_text(
                str(day),
                size=12,
                color=ft.Colors.WHITE if selected else self.foreground,
            ),
        )

    def _pick_day(self, value: dt.date) -> None:
        self.calendar_selected = value
        self._render_calendar()

    def _select_today(self, event: ft.ControlEvent) -> None:
        today = dt.date.today()
        self.calendar_selected = today
        self.calendar_year = today.year
        self.calendar_month = today.month
        self.calendar_mode = "month"
        self._render_calendar()

    def _confirm_calendar_date(self, event: ft.ControlEvent) -> None:
        apply = self.calendar_apply
        value = self.calendar_selected
        self._close_calendar()
        if apply is not None:
            apply(value)
        self.page.update()

    def _clear_calendar_date(self, event: ft.ControlEvent) -> None:
        apply = self.calendar_apply
        self._close_calendar()
        if apply is not None:
            apply(None)
        self.page.update()

    def _previous_month(self, event: ft.ControlEvent) -> None:
        self._shift_month(-1)

    def _next_month(self, event: ft.ControlEvent) -> None:
        self._shift_month(1)

    def _shift_month(self, delta: int) -> None:
        month = self.calendar_month + delta
        year = self.calendar_year
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        self.calendar_year = year
        self.calendar_month = month
        self._render_calendar()

    def _on_entry_change(self, event: ft.ControlEvent) -> None:
        self._entry_auto = False

    def _sync_entry_from_anime(self) -> None:
        """条目为自动生成时，按动画字段首词重新生成。"""
        if not self._entry_auto:
            return
        anime = (self.anime_field.value or "").strip()
        parts = anime.split()
        self.entry_field.value = parts[0] if parts else ""
        self._entry_auto = True
        try:
            self.entry_field.update()
        except Exception:
            pass

    def _on_anime_change(self, event: ft.ControlEvent) -> None:
        if self._suppress_anime_change:
            return
        current = (self.anime_field.value or "").strip()
        previous = self._anime_previous.strip()
        entry = (self.entry_field.value or "").strip()
        if current != previous:
            if not current:
                if self._entry_auto:
                    self.entry_field.value = ""
                    try:
                        self.entry_field.update()
                    except Exception:
                        pass
            elif self._entry_auto or not entry or entry == previous:
                parts = current.split()
                first = parts[0] if parts else ""
                if first:
                    self.entry_field.value = first
                    self._entry_auto = True
                    try:
                        self.entry_field.update()
                    except Exception:
                        pass
        self._anime_previous = current
        self._refresh_cover_buttons()
        self._refresh_former_name_label()
        self._anime_dirty = True

    def _refresh_former_name_label(self) -> None:
        current = (self.anime_field.value or "").strip()
        show = (
            bool(self.former_name)
            and current != self.former_name
        )
        self.former_name_label.value = (
            f"曾用名：{self.former_name}" if show else ""
        )
        self.former_name_label.visible = show
        self.former_name_container.visible = show
        try:
            self.former_name_container.update()
        except Exception:
            pass

    def _apply_former_name(self, event: ft.ControlEvent) -> None:
        name = str(self.former_name or "").strip()
        if not name:
            return
        self._suppress_anime_change = True
        try:
            self.anime_field.value = name
            self.anime_field.update()
        except Exception:
            pass
        finally:
            self._suppress_anime_change = False
        self._anime_previous = name
        self._refresh_former_name_label()
        self._refresh_cover_buttons()

    def _commit_anime_search(
        self,
        event: ft.ControlEvent | None = None,
        *,
        force: bool = False,
    ) -> None:
        if self._suppress_anime_change:
            return
        if not force and not self._anime_dirty:
            return
        if not is_attached(self.bgm_results):
            return
        keyword = (self.anime_field.value or "").strip()
        self._anime_dirty = False
        self._bgm_token += 1
        token = self._bgm_token
        if not keyword:
            self._clear_bgm_results()
            return
        self.page.run_task(self._search_anime, keyword, token)

    async def _search_anime(self, keyword: str, token: int) -> None:
        results = await asyncio.to_thread(search_bgm, keyword)
        if token != self._bgm_token:
            return
        if (self.anime_field.value or "").strip() != keyword:
            return
        if not is_attached(self.bgm_results):
            return
        self._render_bgm_results(results)

    def _render_bgm_results(
        self,
        results: list[dict[str, object]],
    ) -> None:
        self.bgm_choices = {
            int(item["id"]): item
            for item in results
            if isinstance(item.get("id"), int)
        }
        buttons: list[ft.Control] = []
        for item in results:
            label = str(
                item.get("name_cn") or item.get("name") or ""
            ).strip()
            if not label:
                continue
            buttons.append(
                ft.Button(
                    content=ui_text(label, size=12),
                    height=34,
                    on_click=(
                        lambda event, choice=item: (
                            self._apply_bgm_result(choice)
                        )
                    ),
                )
            )
        self.bgm_results.controls = (
            [
                ft.Row(
                    wrap=True,
                    spacing=6,
                    run_spacing=6,
                    controls=buttons,
                )
            ]
            if buttons
            else []
        )
        try:
            self.bgm_results.update()
        except Exception:
            pass

    def _clear_bgm_results(self) -> None:
        self.bgm_choices = {}
        self.bgm_results.controls = []
        try:
            self.bgm_results.update()
        except Exception:
            pass

    def _apply_bgm_result(self, item: dict[str, object]) -> None:
        label = str(
            item.get("name_cn") or item.get("name") or ""
        ).strip()
        if not label:
            return
        subject_id = item.get("id")
        self.selected_bgm_id = (
            subject_id if isinstance(subject_id, int) else None
        )
        self.bgm_id = (
            subject_id if isinstance(subject_id, int) else -1
        )
        self._refresh_cover_buttons()
        self._suppress_anime_change = True
        try:
            self.anime_field.value = label
            self._anime_previous = label.strip()
            self.anime_field.update()
        except Exception:
            pass
        finally:
            self._suppress_anime_change = False
        self._anime_dirty = False
        # 条目为空时按「动画首词」自动生成，并保持自动跟随。
        if not (self.entry_field.value or "").strip():
            self._entry_auto = True
        self._sync_entry_from_anime()
        self._refresh_former_name_label()
        if isinstance(subject_id, int):
            self._bgm_detail_token += 1
            token = self._bgm_detail_token
            self._show_bgm_loading()
            self.page.run_task(
                self._load_bgm_details,
                subject_id,
                token,
            )

    def _show_bgm_loading(self) -> None:
        self._hide_bgm_loading()
        ring = ft.Container(
            left=24,
            bottom=24,
            width=44,
            height=44,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(
                width=26,
                height=26,
                stroke_width=3,
                color=ft.Colors.BLUE,
            ),
        )
        self._bgm_loading = ring
        try:
            self.page.overlay.append(ring)
            self.page.update()
        except Exception:
            self._bgm_loading = None

    def _hide_bgm_loading(self) -> None:
        ring = self._bgm_loading
        self._bgm_loading = None
        if ring is None:
            return
        try:
            if ring in self.page.overlay:
                self.page.overlay.remove(ring)
            self.page.update()
        except Exception:
            pass

    async def _load_bgm_details(
        self,
        subject_id: int,
        token: int,
    ) -> None:
        try:
            info = await asyncio.to_thread(
                _fetch_bgm_info,
                subject_id,
                (self.anime_field.value or "").strip(),
                set(self.preferences.fixed_columns),
            )
            if token != self._bgm_detail_token:
                return
            if not is_attached(self.bgm_results):
                return
            self._apply_bgm_info(info, overwrite=True)
        finally:
            if token == self._bgm_detail_token:
                self._hide_bgm_loading()

    def _apply_bgm_info(
        self,
        info: dict[str, object],
        *,
        overwrite: bool = False,
    ) -> None:
        fixed = set(self.preferences.fixed_columns)

        def allowed(key: str) -> bool:
            return key not in fixed

        spec = str(info.get("规格") or "").strip()
        if allowed("specification") and spec and (
            overwrite or not str(self.spec_field.value or "").strip()
        ):
            self.spec_field.value = spec

        category = str(info.get("类型") or "").strip()
        if allowed("category") and category and (
            overwrite or not self.category_value.strip()
        ):
            self.category_value = category
            self.category_label.value = category

        staff_info = info.get("STAFF")
        if allowed("staff") and isinstance(staff_info, dict):
            current_has = any(
                str(key.value or "").strip()
                or str(value.value or "").strip()
                for key, value in self.staff_pairs
            )
            if overwrite or not current_has:
                # 按字典顺序重建键值对。
                self.staff_pairs = []
                for key, value in staff_info.items():
                    key_field, value_field = self._new_staff_pair()
                    key_field.value = str(key)
                    value_field.value = str(value)
                    self.staff_pairs.append(
                        (key_field, value_field)
                    )
                if not self.staff_pairs:
                    self.staff_pairs = [self._new_staff_pair()]
                self._rebuild_staff()

        rating = info.get("评分")
        if allowed("rating") and isinstance(rating, int) and not isinstance(rating, bool):
            if overwrite or not str(self.score_field.value or "").strip():
                self.score_field.value = str(rating)

        raw_tags = info.get("TAG")
        tags = (
            [
                str(tag).strip()
                for tag in raw_tags
                if str(tag).strip()
            ]
            if isinstance(raw_tags, list)
            else []
        )
        existing_tags = any(
            str(text_field.value or "").strip()
            for text_field in self.tag_fields
        )
        if allowed("tag") and tags and (overwrite or not existing_tags):
            self.tag_fields = [
                self._text_field(hint_text=HINT_TAG)
                for _ in range(len(tags))
            ]
            for text_field, value in zip(self.tag_fields, tags):
                text_field.value = value
            self._rebuild_text_list(
                self.tag_fields, self.tag_column, self._add_tag
            )

        studios = [
            value.strip()
            for value in str(info.get("制作公司") or "").split("×")
            if value.strip()
        ]
        existing_studios = any(
            str(text_field.value or "").strip()
            for text_field in self.studio_fields
        )
        if allowed("studio") and studios and (overwrite or not existing_studios):
            self.studio_fields = [
                self._text_field(hint_text=HINT_STUDIO)
                for _ in range(len(studios))
            ]
            for text_field, value in zip(self.studio_fields, studios):
                text_field.value = value
            self._rebuild_text_list(
                self.studio_fields,
                self.studio_column,
                self._add_studio,
            )

        role_text = str(info.get("角色") or "").strip()
        pairs: list[tuple[str, list[str]]] = [
            (name, cvs)
            for name, cvs in parse_roles(role_text)
            if name
        ]
        existing_roles = any(
            str(name_field.value or "").strip()
            or str(cv_field.value or "").strip()
            for name_field, cv_field in self.role_pairs
        )
        if allowed("role") and pairs and (overwrite or not existing_roles):
            self.role_pairs = []
            for name, cvs in pairs:
                name_field = self._text_field(hint_text=HINT_ROLE)
                cv_field = self._text_field(hint_text=HINT_CV)
                name_field.value = name
                cv_field.value = "/".join(cvs) if cvs else "无"
                self.role_pairs.append((name_field, cv_field))
            self._rebuild_role()

        broadcast = str(info.get("放送") or "").strip()
        if allowed("broadcast") and broadcast and (
            overwrite or not self._broadcast_text().strip()
        ):
            self._apply_broadcast(broadcast)

        self.skip_fill_checkbox.value = True
        self.page.update()

    def _open_bgm_page(self, event: ft.ControlEvent) -> None:
        if self.bgm_id == -1:
            return
        url = f"https://bgm.tv/subject/{self.bgm_id}"
        launcher = None
        for service in self.page.services:
            if isinstance(service, ft.UrlLauncher):
                launcher = service
                break
        if launcher is None:
            launcher = ft.UrlLauncher()
            self.page.services.append(launcher)
        self.page.run_task(launcher.launch_url, url)

    def _open_network_fill_dialog(
        self, event: ft.ControlEvent
    ) -> None:
        labels = (
            "输入页面ID",
            "打开网页",
            f"当前ID: {self.bgm_id}",
        )
        width = max(
            text_width(label, size=14) for label in labels
        ) + 48
        width = max(width, 240)

        def open_id(event: ft.ControlEvent) -> None:
            self.page.pop_dialog()
            self._open_bgm_id_dialog(event)

        def open_web(event: ft.ControlEvent) -> None:
            self._open_bgm_page(event)

        dialog = ft.AlertDialog(
            title=ui_text("从 Bangumi 网站导入"),
            content=ft.Container(
                width=width,
                content=ft.Column(
                    spacing=10,
                    horizontal_alignment=(
                        ft.CrossAxisAlignment.STRETCH
                    ),
                    controls=[
                        ft.Button(
                            content=ui_text("输入页面ID"),
                            width=width,
                            on_click=open_id,
                        ),
                        ft.Button(
                            content=ui_text("打开网页"),
                            width=width,
                            disabled=self.bgm_id == -1,
                            on_click=open_web,
                        ),
                        ui_text(
                            f"当前ID: {self.bgm_id}",
                            size=13,
                            width=width,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            ),
            actions=[
                ft.Button(
                    content=ui_text("确定"),
                    on_click=lambda event: self.page.pop_dialog(),
                )
            ],
        )
        self.page.show_dialog(dialog)

    def _open_bgm_id_dialog(self, event: ft.ControlEvent) -> None:
        field = ft.TextField(
            label="Bangumi 页面 ID",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            autofocus=True,
        )
        dialog = ft.AlertDialog(
            title=ui_text("输入 Bangumi ID"),
            content=field,
            actions=[],
        )

        def cancel(event: ft.ControlEvent) -> None:
            self.page.pop_dialog()

        def confirm(event: ft.ControlEvent) -> None:
            self.page.pop_dialog()
            text = (field.value or "").strip()
            if not text.isdigit():
                show_error_dialog(
                    self.page,
                    title="ID 无效",
                    message="请输入纯数字 ID",
                )
                return
            self.page.run_task(
                self._load_bgm_id_info,
                int(text),
            )

        field.on_submit = confirm
        dialog.actions = [
            ft.TextButton(content=ui_text("取消"), on_click=cancel),
            ft.Button(content=ui_text("确定"), on_click=confirm),
        ]
        self.page.show_dialog(dialog)

    async def _load_bgm_id_info(self, subject_id: int) -> None:
        self._show_bgm_loading()
        try:
            info = await asyncio.to_thread(
                _fetch_bgm_info,
                subject_id,
                (self.anime_field.value or "").strip(),
                set(self.preferences.fixed_columns),
            )
        except Exception as exc:
            # 网络/解析异常统一给出弹窗反馈。
            show_error_dialog(
                self.page,
                title="获取失败",
                message=f"网络请求失败：{exc}",
            )
            return
        finally:
            self._hide_bgm_loading()
        error = str(info.get("error") or "").strip()
        if error:
            show_error_dialog(
                self.page,
                title="获取失败",
                message=error,
            )
            return
        fields = (
            "规格",
            "类型",
            "TAG",
            "STAFF",
            "制作公司",
            "放送",
            "角色",
            "评分",
        )
        if not any(
            (
                bool(value)
                if isinstance(value, dict)
                else str(value or "").strip()
            )
            for value in (info.get(key) for key in fields)
        ):
            show_error_dialog(
                self.page,
                title="获取失败",
                message="无法获取该 ID 的动画信息，请检查 ID",
            )
            return
        previous_anime = (self.anime_field.value or "").strip()
        if self.original_record is not None and previous_anime:
            self.former_name = previous_anime
        previous_entry = (self.entry_field.value or "").strip()
        self._clear_import_fields()
        name = str(
            info.get("name_cn") or info.get("name") or ""
        ).strip()
        if name:
            if "anime" not in self.preferences.fixed_columns:
                self.anime_field.value = name
                self._anime_previous = name.strip()
            if (
                self._entry_auto
                or not previous_entry
                or previous_entry == previous_anime
            ):
                parts = name.split()
                first = parts[0] if parts else ""
                if first:
                    self.entry_field.value = first
                    self._entry_auto = True
        self.bgm_id = subject_id
        self._apply_bgm_info(info, overwrite=True)
        self._refresh_former_name_label()
        self._refresh_cover_buttons()
        show_toast(self.page, "导入成功")

    def _cover_exists(self) -> bool:
        return has_cover(self.bgm_id)

    def _cover_icon_controls(self) -> list[ft.Control]:
        exists = self._cover_exists()
        return [
            hover_icon(
                self.page,
                ft.Icons.DOWNLOAD,
                tooltip="获取封面",
                on_click=self._fetch_cover,
                size=20,
                padding=8,
            ),
            hover_icon(
                self.page,
                ft.Icons.SEARCH,
                tooltip="查看封面",
                on_click=self._view_cover,
                size=20,
                padding=8,
                disabled=not exists,
            ),
            hover_icon(
                self.page,
                ft.Icons.DELETE_OUTLINE,
                tooltip="删除封面",
                on_click=self._delete_cover,
                size=20,
                padding=8,
                disabled=not exists,
                color=ft.Colors.RED,
            ),
        ]

    def _refresh_cover_buttons(self) -> None:
        row = getattr(self, "cover_icons_row", None)
        if row is None:
            return
        label = getattr(self, "cover_label", None)
        row.controls = (
            ([label] if label is not None else [])
            + self._cover_icon_controls()
        )
        try:
            row.update()
        except Exception:
            pass

    def _fetch_cover(self, event: ft.ControlEvent) -> None:
        if self.bgm_id == -1:
            show_error_dialog(
                self.page,
                title="封面图",
                message="没有动画ID，请通过点击提供的动画自动填充后更新ID",
            )
            return
        self._show_bgm_loading()
        self.page.run_task(self._fetch_cover_task, self.bgm_id)

    async def _fetch_cover_task(self, subject_id: int) -> None:
        try:
            path = await asyncio.to_thread(
                save_subject_image,
                subject_id,
            )
            row = getattr(self, "cover_icons_row", None)
            if row is None or not is_attached(row):
                return
            if path is None:
                show_error_dialog(
                    self.page,
                    title="封面图",
                    message="获取封面图失败",
                )
                return
            invalidate_cover(subject_id)
            self._refresh_cover_buttons()
            show_toast(self.page, "封面图获取成功")
        finally:
            self._hide_bgm_loading()

    def _view_cover(self, event: ft.ControlEvent) -> None:
        path = cover_path(self.bgm_id) if self.bgm_id != -1 else None
        if path is None or not path.is_file():
            show_error_dialog(
                self.page,
                title="封面图",
                message="还没有封面图",
            )
            return
        try:
            data = path.read_bytes()
        except OSError:
            show_error_dialog(
                self.page,
                title="封面图",
                message="读取封面图失败",
            )
            return
        show_image_preview(self.page, data)

    def _delete_cover(self, event: ft.ControlEvent) -> None:
        path = cover_path(self.bgm_id) if self.bgm_id != -1 else None
        if path is not None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        if self.bgm_id != -1:
            invalidate_cover(self.bgm_id)
        self._refresh_cover_buttons()
        show_toast(self.page, "封面图已删除")

    # ------------------------------------------------------------------
    # 页面组装
    # ------------------------------------------------------------------

    def _build_card(self) -> ft.Container:
        self.cover_label = ui_text(
            "封面",
            size=14,
            weight=ft.FontWeight.BOLD,
        )
        self.cover_icons_row = ft.Row(
            spacing=8,
            run_spacing=8,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[self.cover_label, *self._cover_icon_controls()],
        )
        controls: list[ft.Control] = [
            self._field("条目", self.entry_field, key="entry"),
            ft.Row(
                controls=[
                    ft.Button(
                        content=ui_text("从网络填充"),
                        on_click=self._open_network_fill_dialog,
                        expand=True,
                    )
                ],
            ),
            self._field("动画", self.anime_field, key="anime"),
            self.former_name_container,
            self.bgm_results,
            self._field("制作公司", self.studio_column, key="studio"),
            self._field("类型", self.category_button),
            self._field("规格", self.spec_block, key="spec"),
            self._field("TAG", self.tag_column, key="tag"),
            self._field("放送", self.broadcast_column),
            self._field("STAFF", self.staff_column, key="staff"),
            self._field("角色", self.role_column, key="role"),
            self._field("评分", self.score_field, key="score"),
            self._field("补完", self.completion_block),
            self._field("备注", self.remark_field),
            self.sequel_checkbox,
            self.skip_fill_checkbox,
            self.cover_icons_row,
            ft.Row(
                spacing=12,
                alignment=(
                    ft.MainAxisAlignment.SPACE_BETWEEN
                    if self.on_delete is not None
                    else ft.MainAxisAlignment.END
                ),
                controls=[
                    *(
                        [
                            ft.Row(
                                spacing=12,
                                controls=[
                                    ft.Button(
                                        content=ui_text(
                                            "删除",
                                            color=ft.Colors.WHITE,
                                        ),
                                        bgcolor=ft.Colors.RED,
                                        on_click=self._request_delete,
                                    ),
                                    ft.Button(
                                        content=ui_text("重置内容"),
                                        on_click=self._reset_content,
                                    ),
                                ],
                            )
                        ]
                        if self.on_delete is not None
                        else []
                    ),
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.Button(
                                content=ui_text(
                                    "确认", color=ft.Colors.WHITE
                                ),
                                bgcolor=ft.Colors.BLUE,
                                on_click=self._confirm,
                            ),
                            ft.OutlinedButton(
                                content=ui_text(
                                    "取消", color=self.foreground
                                ),
                                style=ft.ButtonStyle(
                                    color=self.foreground,
                                    side=ft.BorderSide(1, self.border),
                                    shape=ft.RoundedRectangleBorder(
                                        radius=8
                                    ),
                                    padding=ft.Padding.symmetric(
                                        horizontal=18, vertical=12
                                    ),
                                ),
                                on_click=self._cancel,
                            ),
                        ],
                    ),
                ],
            ),
        ]

        return ft.Container(
            bgcolor=background_color(self.page),
            border=ft.Border.all(1, self.border),
            border_radius=12,
            padding=20,
            content=ft.Column(spacing=FIELD_SPACING, controls=controls),
        )

    def _validated_fields(self) -> list[ft.TextField]:
        fields = [
            self.entry_field,
            self.anime_field,
            self.spec_field,
            self.score_field,
        ]
        fields.extend(self.tag_fields)
        fields.extend(self.studio_fields)
        for key_field, value_field in self.staff_pairs:
            fields.extend([key_field, value_field])
        for name_field, cv_field in self.role_pairs:
            fields.extend([name_field, cv_field])
        return fields

    def _reset_validation(self) -> None:
        for error in self.error_labels.values():
            error.value = ""
            error.visible = False
        for field in self._validated_fields():
            field.border_color = self.border
            field.focused_border_color = ft.Colors.BLUE

    def _show_error(self, key: str, message: str) -> None:
        error = self.error_labels.get(key)
        if error is not None:
            error.value = message
            error.visible = True

    def _mark_invalid(self, field: ft.TextField) -> None:
        field.border_color = ft.Colors.RED
        field.focused_border_color = ft.Colors.RED

    def _validate_required(
        self,
        key: str,
        field: ft.TextField,
        label: str,
        limit: int,
    ) -> None:
        text = (field.value or "").strip()
        if not text:
            self._show_error(key, f"{label}不能为空")
            self._mark_invalid(field)
        elif len(text) > limit:
            self._show_error(key, f"{label}不能超过{limit}个字符")
            self._mark_invalid(field)

    def _validate_length(
        self,
        key: str,
        field: ft.TextField,
        label: str,
        limit: int,
    ) -> None:
        if len((field.value or "").strip()) > limit:
            self._show_error(key, f"{label}不能超过{limit}个字符")
            self._mark_invalid(field)

    def _validate_lines(
        self,
        key: str,
        fields: list[ft.TextField],
        message: str,
        limit: int,
    ) -> None:
        invalid = [
            field
            for field in fields
            if len((field.value or "").strip()) > limit
        ]
        if not invalid:
            return
        self._show_error(key, message)
        for field in invalid:
            self._mark_invalid(field)

    def _validate_role(self, limit: int) -> None:
        invalid: list[ft.TextField] = []
        for name_field, cv_field in self.role_pairs:
            for field in (name_field, cv_field):
                if len((field.value or "").strip()) > limit:
                    invalid.append(field)
        if not invalid:
            return
        self._show_error("role", f"角色每项不能超过{limit}个字符")
        for field in invalid:
            self._mark_invalid(field)

    def _validate_staff(self, limit: int) -> None:
        invalid: list[ft.TextField] = []
        for key_field, _value_field in self.staff_pairs:
            # 只校验职务（第一个输入框），姓名不限制长度。
            if len((key_field.value or "").strip()) > limit:
                invalid.append(key_field)
        if not invalid:
            return
        self._show_error(
            "staff", f"STAFF 职务不能超过{limit}个字符"
        )
        for field in invalid:
            self._mark_invalid(field)

    def _validate(self) -> None:
        self._validate_required("entry", self.entry_field, "条目", 100)
        self._validate_required("anime", self.anime_field, "动画", 100)
        self._validate_length("spec", self.spec_field, "规格", 100)
        self._validate_length("score", self.score_field, "评分", 100)
        self._validate_staff(100)
        self._validate_lines(
            "tag",
            self.tag_fields,
            "TAG每行不能超过100个字符",
            100,
        )
        self._validate_lines(
            "studio",
            self.studio_fields,
            "制作公司每行不能超过100个字符",
            100,
        )
        self._validate_role(100)

    def _build_record(self) -> Record:
        record: Record = {field: "" for field in RECORD_FIELDS}

        anime = (self.anime_field.value or "").strip()
        record["anime"] = anime
        record["former_name"] = self.former_name
        record["entry"] = (self.entry_field.value or "").strip() or anime
        record["specification"] = (
            self.spec_field.value or ""
        ).strip()
        record["category"] = self.category_value
        staff: dict[str, str] = {}
        for key_field, value_field in self.staff_pairs:
            key = str(key_field.value or "").strip()
            value = str(value_field.value or "").strip()
            if key and value:
                staff[key] = value
        record["staff"] = staff
        record["rating"] = _clamp_score_text(
            (self.score_field.value or "").strip()
        )
        record["remark"] = (self.remark_field.value or "").strip()

        studios = [
            (text_field.value or "").strip()
            for text_field in self.studio_fields
        ]
        record["studio"] = STUDIO_SEPARATOR.join(
            value for value in studios if value
        )

        tags = [
            (text_field.value or "").strip()
            for text_field in self.tag_fields
        ]
        seen_tags: set[str] = set()
        unique_tags: list[str] = []
        for tag in tags:
            if not tag:
                continue
            key = tag.casefold()
            if key in seen_tags:
                continue
            seen_tags.add(key)
            unique_tags.append(tag)
        record["tag"] = "\n".join(unique_tags)

        record["broadcast"] = self._broadcast_text()

        names: list[str] = []
        for name_field, cv_field in self.role_pairs:
            name = (name_field.value or "").strip()
            if not name:
                continue
            cv = (cv_field.value or "").strip()
            names.append(f"{name}({cv})" if cv else name)
        record["role"] = "\n".join(names)

        completion = self.completion_date
        record["completion"] = (
            f"{completion.year:04d}.{completion.month:02d}"
            f".{completion.day:02d}"
            if completion is not None
            else ""
        )

        record["sequel"] = bool(self.sequel_checkbox.value)
        record["skip_fill"] = bool(self.skip_fill_checkbox.value)
        record["bgm_id"] = self.bgm_id
        return record

    def _broadcast_text(self) -> str:
        if self.broadcast_mode == BROADCAST_POINT:
            dates = [
                item.point
                for item in self.point_items
                if item.point is not None
            ]
            return " ".join(_date_text(date) for date in dates)

        item = self.range_item
        if item.start is not None and item.end is not None:
            return f"{_date_text(item.start)}~{_date_text(item.end)}"
        single = item.start or item.end
        return _date_text(single) if single is not None else ""

    def _confirm(self, event: ft.ControlEvent) -> None:
        self._reset_validation()
        self._validate()
        if any(error.visible for error in self.error_labels.values()):
            show_toast(
                self.page,
                "请检查表单内容是否合规",
                error=True,
            )
            self.page.update(*self.error_labels.values())
            return

        record = self._build_record()
        if self.on_save is not None:
            try:
                self.on_save(record)
            except Exception as error:
                show_error_dialog(
                    self.page,
                    title="保存失败",
                    message=str(error),
                )
                return

        final_id = to_bgm_id(record.get("bgm_id"))
        if (
            self._pending_cover_delete is not None
            and self._pending_cover_delete != final_id
        ):
            path = cover_path(self._pending_cover_delete)
            if path is not None:
                try:
                    path.unlink()
                except OSError:
                    pass
            invalidate_cover(self._pending_cover_delete)
        self._pending_cover_delete = None

        # 保存成功后：有 Bangumi ID 且本地还没有封面时，询问是否缓存。
        if final_id != -1 and not has_cover(final_id):
            self._ask_cache_cover(final_id)
            return
        self._close_after_save()

    def _close_after_save(self) -> None:
        """保存成功后的关闭动作（原 _confirm 末尾逻辑）。"""
        if self.page.views:
            self.page.views.pop()
        self.page.update()

    def _ask_cache_cover(self, subject_id: int) -> None:
        """询问是否缓存封面；只问一次。"""
        def cancel(event=None) -> None:
            self.page.pop_dialog()
            self._close_after_save()

        def confirm(event=None) -> None:
            self.page.pop_dialog()
            self.page.run_task(
                self._cache_cover_then_close,
                subject_id,
            )

        self.page.show_dialog(
            ft.AlertDialog(
                title=ui_text("封面图"),
                content=ui_text("是否缓存封面图？", size=13),
                actions=[
                    ft.TextButton(
                        content=ui_text("取消"),
                        on_click=cancel,
                    ),
                    ft.Button(
                        content=ui_text("缓存"),
                        on_click=confirm,
                    ),
                ],
            )
        )

    async def _cache_cover_then_close(self, subject_id: int) -> None:
        """等封面缓存完成后再关闭表单，保证列表刷新能读到新封面。"""
        self._show_bgm_loading()
        path = None
        try:
            path = await asyncio.to_thread(
                save_subject_image,
                subject_id,
            )
            invalidate_cover(subject_id)
        except Exception as exc:
            show_error_dialog(
                self.page,
                title="封面图",
                message=f"缓存封面失败：{exc}",
            )
        finally:
            self._hide_bgm_loading()
            self._close_after_save()
        if path is None:
            return
        show_toast(self.page, "封面图缓存成功")

    def _request_delete(self, event: ft.ControlEvent) -> None:
        self.page.show_dialog(
            confirmation_dialog(
                self.page,
                title="删除条目",
                message="确定删除这条记录吗？",
                confirm_label="删除",
                on_confirm=self._confirm_delete,
            )
        )

    def _confirm_delete(self, event: ft.ControlEvent) -> None:
        self.page.pop_dialog()
        if self.on_delete is not None:
            try:
                self.on_delete()
            except Exception as error:
                show_error_dialog(
                    self.page,
                    title="删除失败",
                    message=str(error),
                )
                return

        if self.page.views:
            self.page.views.pop()
        self.page.update()

    def _clear_import_fields(self) -> None:
        fixed = set(self.preferences.fixed_columns)
        clear_all = bool(
            self.preferences.clear_fixed_fields_on_id_import
        )

        def should_clear(key: str) -> bool:
            return clear_all or key not in fixed

        if should_clear("staff"):
            self._reset_staff_pairs()
        if should_clear("specification"):
            self.spec_field.value = ""
        if should_clear("rating"):
            self.score_field.value = ""
        self.remark_field.value = ""
        if should_clear("category"):
            self.category_value = ""
            self.category_label.value = CHOOSE_CATEGORY

        if should_clear("tag"):
            self.tag_fields = [self._text_field(hint_text=HINT_TAG)]
            self._rebuild_text_list(
                self.tag_fields,
                self.tag_column,
                self._add_tag,
            )

        if should_clear("studio"):
            self.studio_fields = [
                self._text_field(hint_text=HINT_STUDIO)
            ]
            self._rebuild_text_list(
                self.studio_fields,
                self.studio_column,
                self._add_studio,
            )

        if should_clear("role"):
            self.role_pairs = [
                (
                    self._text_field(hint_text=HINT_ROLE),
                    self._text_field(hint_text=HINT_CV),
                )
            ]
            self._rebuild_role()

        if should_clear("broadcast"):
            self._apply_broadcast("")
        self.completion_date = None
        self.completion_label.value = CHOOSE_DATE

    def _reset_content(self, event: ft.ControlEvent) -> None:
        previous_name = self.former_name
        old_id = self.bgm_id
        if old_id != -1:
            self._pending_cover_delete = old_id
        self.bgm_id = -1
        self._reset_staff_pairs()
        self.spec_field.value = ""
        self.score_field.value = ""
        self.remark_field.value = ""
        self.category_value = ""
        self.category_label.value = CHOOSE_CATEGORY

        self.tag_fields = [self._text_field(hint_text=HINT_TAG)]
        self._rebuild_text_list(
            self.tag_fields,
            self.tag_column,
            self._add_tag,
        )

        self.studio_fields = [
            self._text_field(hint_text=HINT_STUDIO)
        ]
        self._rebuild_text_list(
            self.studio_fields,
            self.studio_column,
            self._add_studio,
        )

        self.role_pairs = [
            (
                self._text_field(hint_text=HINT_ROLE),
                self._text_field(hint_text=HINT_CV),
            )
        ]
        self._rebuild_role()

        self._apply_broadcast("")
        self.completion_date = None
        self.completion_label.value = CHOOSE_DATE

        self.sequel_checkbox.value = False
        self.skip_fill_checkbox.value = False
        if previous_name:
            self.anime_field.value = previous_name
            self._anime_previous = previous_name.strip()
        self._entry_auto = False
        self.former_name = ""
        self._refresh_former_name_label()

        self._clear_bgm_results()
        self._refresh_cover_buttons()
        self.page.update()

    def _cancel(self, event: ft.ControlEvent) -> None:
        if self.page.views:
            self.page.views.pop()
            self.page.update()


def build_entry_form_view(
    page: ft.Page,
    *,
    record: Record | None = None,
    on_save: Callable[[Record], None] | None = None,
    on_delete: Callable[[], None] | None = None,
    title: str = "条目",
    prefill_anime: str | None = None,
    auto_search: bool = False,
) -> ft.View:
    form = EntryForm(
        page,
        record=record,
        on_save=on_save,
        on_delete=on_delete,
    )
    if prefill_anime:
        form.anime_field.value = prefill_anime
        form._anime_previous = prefill_anime
    view = ft.View(
        route=ENTRY_FORM_ROUTE,
        appbar=ft.AppBar(title=ui_text(title)),
        padding=page_padding(),
        controls=[
            vertical_page(
                [
                    ft.ResponsiveRow(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=0,
                        run_spacing=0,
                        controls=[
                            ft.Container(
                                col=FORM_COLUMNS,
                                content=form.card,
                            )
                        ],
                    )
                ]
            )
        ],
    )
    if auto_search:
        async def run() -> None:
            await asyncio.sleep(0.05)
            form._commit_anime_search(None, force=True)

        page.run_task(run)
    return view


def open_entry_form(
    page: ft.Page,
    *,
    record: Record | None = None,
    on_save: Callable[[Record], None] | None = None,
    on_delete: Callable[[], None] | None = None,
    title: str = "条目",
    prefill_anime: str | None = None,
    auto_search: bool = False,
) -> None:
    """将条目表单压入视图栈，同时保留观影页。"""
    if page.views:
        top = page.views[-1]
        if getattr(top, "route", "") == ENTRY_FORM_ROUTE:
            return

    push_view(
        page,
        build_entry_form_view(
            page,
            record=record,
            on_save=on_save,
            on_delete=on_delete,
            title=title,
            prefill_anime=prefill_anime,
            auto_search=auto_search,
        ),
    )
