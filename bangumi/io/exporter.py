"""观影表格的 Excel 导出。"""

from __future__ import annotations

import unicodedata
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from bangumi.data.watched_data import Record, entry_group_key, split_tags

SHEET_NAME = "bangumi"
FONT_NAME = "宋体"
FONT_SIZE = 11
HEADER_FILL = PatternFill(fill_type="solid", fgColor="D9D9D9")
THIN_SIDE = Side(style="thin", color="FFBFBFBF")
BORDER = Border(
    left=THIN_SIDE,
    right=THIN_SIDE,
    top=THIN_SIDE,
    bottom=THIN_SIDE,
)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")
DATA_ALIGNMENT = Alignment(
    horizontal="center",
    vertical="center",
    wrap_text=False,
)
ENTRY_ALIGNMENT = Alignment(
    horizontal="center",
    vertical="center",
    wrap_text=False,
)
ROLE_ALIGNMENT = Alignment(
    horizontal="left",
    vertical="center",
    wrap_text=True,
)
REMARK_ALIGNMENT = Alignment(
    horizontal="left",
    vertical="center",
    wrap_text=False,
)
MIN_COLUMN_WIDTH = 8
COLUMN_WIDTH_PADDING = 2
HEADER_ROW_HEIGHT = 20
MIN_ROW_HEIGHT = 16
LINE_HEIGHT = 15


def _role_lines(record: Record) -> list[str]:
    from bangumi.data.role_core import role_lines

    return role_lines(
        str(record.get("role", "") or "")
    )


def _merged_role_lines(records: list[Record]) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for record in records:
        for line in _role_lines(record):
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
    return lines


def _cell_text(record: Record, key: str) -> str:
    if key == "entry":
        value = record.get("entry") or record.get("anime") or ""
        return str(value)
    if key == "tag":
        return ", ".join(split_tags(str(record.get("tag", "") or "")))
    if key == "role":
        return "\n".join(_role_lines(record))
    value = record.get(key, "")
    return "" if value is None else str(value)


def _display_width(text: str) -> int:
    """使用类 Excel 字符宽度返回最宽行的长度。"""
    if not text:
        return 0
    widest = 0
    for line in text.split("\n"):
        width = 0
        for char in line:
            wide = unicodedata.east_asian_width(char) in ("W", "F", "A")
            width += 2 if wide else 1
        widest = max(widest, width)
    return widest


def _row_height(values: list[str]) -> int:
    lines = max(
        1,
        max((value.count("\n") + 1 for value in values), default=1),
    )
    return max(MIN_ROW_HEIGHT, lines * LINE_HEIGHT + 2)


def build_workbook_bytes(
    records: list[Record],
    columns: list[tuple[str, str]],
    merge: bool,
) -> bytes:
    """返回包含指定记录与列的 ``.xlsx`` 工作簿。"""
    keys = [
        key
        for key, _ in columns
        if key not in ("number", "sequel")
    ]
    labels = {key: label for key, label in columns}

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME

    widths = [
        _display_width(labels.get(key, key))
        for key in keys
    ]
    for index, key in enumerate(keys, start=1):
        cell = sheet.cell(row=1, column=index)
        cell.value = labels.get(key, key)
        cell.data_type = "s"
        cell.font = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = HEADER_ALIGNMENT
    sheet.row_dimensions[1].height = HEADER_ROW_HEIGHT

    entry_index = keys.index("entry") + 1 if "entry" in keys else None
    role_index = (
        keys.index("role") + 1 if "role" in keys else None
    )

    for offset, record in enumerate(records):
        row = offset + 2
        values = [_cell_text(record, key) for key in keys]
        red = record.get("sequel") is True
        data_font = Font(
            name=FONT_NAME,
            size=FONT_SIZE,
            color="FFFF0000" if red else None,
        )
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index)
            cell.value = value
            cell.data_type = "s"
            cell.font = data_font
            cell.border = BORDER
            if keys[index - 1] == "entry":
                cell.alignment = ENTRY_ALIGNMENT
            elif keys[index - 1] == "role":
                cell.alignment = ROLE_ALIGNMENT
            elif keys[index - 1] == "remark":
                cell.alignment = REMARK_ALIGNMENT
            else:
                cell.alignment = DATA_ALIGNMENT
            widths[index - 1] = max(
                widths[index - 1],
                _display_width(value),
            )
        sheet.row_dimensions[row].height = _row_height(values)

    if "bgm_id" not in keys:
        bgm_column = len(keys) + 1
        header = sheet.cell(row=1, column=bgm_column)
        header.value = "Bangumi页面ID"
        header.data_type = "s"
        header.font = Font(name=FONT_NAME, size=FONT_SIZE, bold=True)
        header.fill = HEADER_FILL
        header.border = BORDER
        header.alignment = HEADER_ALIGNMENT
        for offset, record in enumerate(records):
            cell = sheet.cell(row=offset + 2, column=bgm_column)
            cell.value = int(record.get("bgm_id", -1) or -1)
            cell.data_type = "n"
            cell.border = BORDER
            cell.alignment = DATA_ALIGNMENT
        letter = get_column_letter(bgm_column)
        sheet.column_dimensions[letter].width = 14
        sheet.column_dimensions[letter].hidden = True

    if merge and records:
        groups: list[tuple[int, int]] = []
        start = 0
        for offset in range(1, len(records) + 1):
            if (
                offset == len(records)
                or entry_group_key(records[offset])
                != entry_group_key(records[start])
            ):
                groups.append((start, offset))
                start = offset

        for start_offset, end_offset in groups:
            if end_offset - start_offset <= 1:
                continue
            start_row = start_offset + 2
            end_row = end_offset + 1
            if entry_index is not None:
                sheet.merge_cells(
                    start_row=start_row,
                    start_column=entry_index,
                    end_row=end_row,
                    end_column=entry_index,
                )
            if role_index is None:
                continue
            lines = _merged_role_lines(
                records[start_offset:end_offset]
            )
            cell = sheet.cell(row=start_row, column=role_index)
            cell.value = "\n".join(lines)
            cell.data_type = "s"
            cell.alignment = ROLE_ALIGNMENT
            sheet.merge_cells(
                start_row=start_row,
                start_column=role_index,
                end_row=end_row,
                end_column=role_index,
            )
            height = len(lines) * LINE_HEIGHT + 2
            current = sheet.row_dimensions[start_row].height or 0
            sheet.row_dimensions[start_row].height = max(
                MIN_ROW_HEIGHT,
                current,
                height,
            )
            widths[role_index - 1] = max(
                widths[role_index - 1],
                _display_width(cell.value),
            )

    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = max(
            MIN_COLUMN_WIDTH,
            int(width * 1.1) + 4,
        )

    sheet.freeze_panes = "A2"
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
