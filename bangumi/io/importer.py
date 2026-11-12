"""从 CSV、XLS 和 XLSX 文件导入观影记录。"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl
import xlrd

from bangumi.core.utils import to_bgm_id
from bangumi.data.dates import parse_iso_date as _parse_date
from bangumi.data.watched_data import (
    DETAIL_FIELDS,
    RECORD_FIELDS,
    WATCHED_COLUMNS,
    Record,
    split_tags,
)

MERGED_CELLS_MESSAGE = (
    "检测到有合并单元格。\n"
    "若需用于导入，请在导出时取消勾选「合并同一部番」"
)

CATEGORY_OPTIONS = (
    "小说改",
    "漫画改",
    "游戏改",
    "原创",
    "电影",
    "跨媒体",
    "音乐衍生",
    "其他",
)


def import_records(
    data: bytes,
    filename: str,
) -> tuple[list[Record], dict[str, int]]:
    rows = _read_import_rows(data, filename)
    if not rows:
        raise ValueError("导入文件没有有效内容")

    _, headers, _ = rows[0]
    header_indexes = _map_import_headers(headers)
    branch_mode = {"main_entry", "branches"}.issubset(header_indexes)
    anime_mode = "anime" in header_indexes
    if branch_mode or anime_mode:
        data_rows = rows[1:]
    else:
        data_rows = rows
    imported_records: list[Record] = []
    for line_number, values, row_is_red in data_rows:
        if branch_mode or anime_mode:
            row = {
                field: _value_at(values, column_index)
                for field, column_index in header_indexes.items()
            }
        else:
            row = {"anime": _value_at(values, 0)}
        if not branch_mode:
            if (
                not str(row.get("anime") or "").strip()
                and not str(row.get("specification") or "").strip()
            ):
                continue

        specification = str(row.get("specification") or "").strip()
        if specification:
            row["specification"] = _append_episode_labels(
                specification
            )

        if branch_mode:
            expanded = _expand_branch_row(row, row_is_red, line_number)
            for branch in expanded:
                branch["bgm_id"] = to_bgm_id(row.get("bgm_id"))
            imported_records.extend(expanded)
            continue

        record: Record = {field: "" for field in RECORD_FIELDS}
        for field in RECORD_FIELDS:
            if field in row:
                record[field] = row[field]
        record["sequel"] = row_is_red
        record["bgm_id"] = to_bgm_id(row.get("bgm_id"))
        record["entry"] = (
            row.get("entry")
            or row.get("main_entry")
            or record["anime"]
        )
        imported_records.append(record)

    stats: dict[str, int] = {
        "missing_anime": 0,
        "missing_spec": 0,
        "missing_broadcast": 0,
        "missing_category": 0,
        "duplicate_anime": 0,
        "invalid_broadcast": 0,
        "invalid_completion": 0,
        "invalid_category": 0,
        "invalid_rating": 0,
    }
    for record in imported_records:
        record["entry"] = _entry_text(str(record.get("entry", "")))
        seen_tags: set[str] = set()
        unique_tags: list[str] = []
        for tag in split_tags(record.get("tag")):
            key = tag.strip().casefold()
            if not key or key in seen_tags:
                continue
            seen_tags.add(key)
            unique_tags.append(tag)
        record["tag"] = "\n".join(unique_tags)
        if not str(record.get("anime") or "").strip():
            stats["missing_anime"] += 1
        if not str(record.get("specification") or "").strip():
            stats["missing_spec"] += 1

        category = str(record.get("category") or "").strip()
        if not category:
            stats["missing_category"] += 1
        elif category not in CATEGORY_OPTIONS:
            stats["invalid_category"] += 1
        record["category"] = (
            category if category in CATEGORY_OPTIONS else "其他"
        )

        rating_text = str(record.get("rating", ""))
        if rating_text.strip() and not _rating_valid(rating_text):
            stats["invalid_rating"] += 1
        record["rating"] = _normalize_rating(rating_text)

        broadcast_text = str(record.get("broadcast", ""))
        if not broadcast_text.strip():
            stats["missing_broadcast"] += 1
        normalized_broadcast = _normalize_broadcast(broadcast_text)
        if broadcast_text.strip() and not normalized_broadcast:
            stats["invalid_broadcast"] += 1
        record["broadcast"] = normalized_broadcast

        completion_text = str(record.get("completion", ""))
        normalized_completion = _normalize_completion(completion_text)
        if completion_text.strip() and not normalized_completion:
            stats["invalid_completion"] += 1
        record["completion"] = normalized_completion

    anime_counts = Counter(
        str(record.get("anime") or "").strip().casefold()
        for record in imported_records
    )
    stats["duplicate_anime"] = sum(
        count for count in anime_counts.values() if count > 1
    )

    return imported_records, stats


def _append_episode_labels(value: str) -> str:
    """为纯整数的规格片段追加“话”。"""
    lines: list[str] = []
    for line in value.split("\n"):
        parts: list[str] = []
        for part in re.split(r"[+＋]", line):
            part = part.strip()
            if not part:
                continue
            parts.append(f"{part}话" if part.isdecimal() else part)
        lines.append(" + ".join(parts))
    return "\n".join(lines)


_TIME_SUFFIX = re.compile(r"\s+\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?")
_CHINESE_DATE = re.compile(r"^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日$")
_NUMERIC_DATE = re.compile(
    r"^(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})$"
)
_MONTH_DAY = re.compile(r"^(\d{1,2})\s*月\s*(\d{1,2})\s*日$")
_DATE_SEPARATORS = re.compile(r"[\s,，、;；|]+")


def _entry_text(value: str) -> str:
    """将条目文本中的换行展平并合并空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_rating(value: str) -> str:
    """将导入的评分转换为表格用的、截断到范围内的整数文本。"""
    text = (value or "").strip()
    if not text:
        return ""
    if text.isdecimal():
        rating = int(text)
    else:
        match = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text)
        if match is None:
            return "0"
        number = Decimal(text)
        if "." in text:
            fraction = text.partition(".")[2]
            number *= 10 if len(fraction) == 1 else 100
        rating = int(number)
    if rating < 0:
        return "0"
    if rating > 100:
        return "100"
    return str(rating)


def _rating_valid(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text) is None:
        return False
    try:
        number = Decimal(text)
    except Exception:
        return False
    if "." in text:
        fraction = text.partition(".")[2]
        number *= 10 if len(fraction) == 1 else 100
    return 0 <= int(number) <= 100


def _date_text(value: dt.date) -> str:
    return f"{value.year:04d}年{value.month:02d}月{value.day:02d}日"


def _strip_time_suffix(value: str) -> str:
    return _TIME_SUFFIX.sub("", value or "").strip()


def _parse_month_day(value: str) -> tuple[int, int] | None:
    match = _MONTH_DAY.match(_strip_time_suffix(value))
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _normalize_broadcast(value: str) -> str:
    """规范化导入的放送日期；无效输入转为空。"""
    text = _strip_time_suffix(value)
    if not text:
        return ""

    if "~" in text:
        parts = text.split("~")
        if len(parts) != 2:
            return ""
        start = _parse_date(parts[0])
        if start is None:
            return ""
        end = _parse_date(parts[1])
        if end is None:
            month_day = _parse_month_day(parts[1])
            if month_day is None:
                return ""
            month, day = month_day
            try:
                end = dt.date(start.year, month, day)
            except ValueError:
                return ""
            if end < start:
                try:
                    end = dt.date(start.year + 1, month, day)
                except ValueError:
                    return ""
        return f"{_date_text(start)}~{_date_text(end)}"

    tokens = [
        token for token in _DATE_SEPARATORS.split(text) if token
    ]
    if not tokens:
        return ""
    dates: list[dt.date] = []
    for token in tokens:
        parsed = _parse_date(token)
        if parsed is None:
            return ""
        dates.append(parsed)
    return " ".join(_date_text(parsed) for parsed in dates)


def _normalize_completion(value: str) -> str:
    """将导入的补完日期规范化为 ``YYYY.MM.DD``。"""
    parsed = _parse_date(value)
    if parsed is None:
        return ""
    return f"{parsed.year:04d}.{parsed.month:02d}.{parsed.day:02d}"


def _read_import_rows(
    data: bytes,
    filename: str,
) -> list[tuple[int, list[str], bool]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        text = data.decode("utf-8-sig")
        parsed: list[tuple[int, list[str], bool]] = []
        reader = csv.reader(io.StringIO(text))
        while True:
            line_number = reader.line_num + 1
            try:
                values = next(reader)
            except StopIteration:
                break
            cleaned = [_clean_text(value) for value in values]
            if any(cleaned):
                parsed.append((line_number, cleaned, False))
        return parsed
    if suffix == ".xlsx":
        workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        try:
            if any(
                len(worksheet.merged_cells.ranges)
                for worksheet in workbook.worksheets
            ):
                raise ValueError(MERGED_CELLS_MESSAGE)
            worksheet = workbook.active
            parsed = []
            for line_number, cells in enumerate(
                worksheet.iter_rows(),
                start=1,
            ):
                values = [_clean_text(cell.value) for cell in cells]
                if any(values):
                    row_is_red = any(
                        bool(values[index])
                        and _is_openpyxl_red(cell.font.color)
                        for index, cell in enumerate(cells)
                    )
                    parsed.append(
                        (line_number, values, row_is_red)
                    )
            return parsed
        finally:
            workbook.close()
    if suffix == ".xls":
        workbook = xlrd.open_workbook(
            file_contents=data,
            formatting_info=True,
        )
        try:
            if any(
                sheet.merged_cells for sheet in workbook.sheets()
            ):
                raise ValueError(MERGED_CELLS_MESSAGE)
            worksheet = workbook.sheet_by_index(0)
            parsed = []
            for row_index in range(worksheet.nrows):
                values = [
                    _clean_text(
                        worksheet.cell_value(
                            row_index,
                            column_index,
                        )
                    )
                    for column_index in range(worksheet.ncols)
                ]
                if any(values):
                    row_is_red = any(
                        bool(values[column_index])
                        and _is_xlrd_red(
                            workbook,
                            worksheet,
                            row_index,
                            column_index,
                        )
                        for column_index in range(worksheet.ncols)
                    )
                    parsed.append(
                        (row_index + 1, values, row_is_red)
                    )
            return parsed
        finally:
            workbook.release_resources()
    raise ValueError("仅支持 CSV、XLS 或 XLSX 文件")


def _map_import_headers(headers: list[str]) -> dict[str, int]:
    aliases = {
        **{key.casefold(): key for key, _ in WATCHED_COLUMNS},
        **{label.casefold(): key for key, label in WATCHED_COLUMNS},
        "条目": "entry",
        "entry": "entry",
        "主条目": "main_entry",
        "主分支": "main_entry",
        "main_entry": "main_entry",
        "分支": "branches",
        "branches": "branches",
        "bangumi页面id": "bgm_id",
        "bgm_id": "bgm_id",
        "bangumi id": "bgm_id",
    }
    mapped: dict[str, int] = {}
    for index, header in enumerate(headers):
        field = aliases.get(header.strip().casefold())
        if field is not None and field not in mapped:
            mapped[field] = index
    return mapped


def _expand_branch_row(
    row: dict[str, str],
    row_is_red: bool,
    line_number: int,
) -> list[Record]:
    branch_names = _split_lines(row.get("branches", ""))
    if not branch_names:
        return []

    details: dict[str, list[str]] = {}
    for field in DETAIL_FIELDS:
        value = row.get(field, "")
        if not value:
            continue
        lines = _split_lines(value)
        if len(branch_names) != 1 and len(lines) != len(branch_names):
            raise ValueError(
                f"Line {line_number} not corresponding to {len(branch_names)}"
            )
        details[field] = lines

    if len(branch_names) == 1:
        detail_counts = {len(lines) for lines in details.values()}
        if len(detail_counts) > 1:
            raise ValueError(
                f"Line {line_number} data not corresponding"
            )
        expansion_count = next(iter(detail_counts), 1)
    else:
        expansion_count = len(branch_names)

    records: list[Record] = []
    for index in range(expansion_count):
        branch_name = (
            branch_names[index]
            if len(branch_names) > 1
            else branch_names[0]
        )
        record: Record = {field: "" for field in RECORD_FIELDS}
        for field in RECORD_FIELDS:
            if field not in (*DETAIL_FIELDS, "anime") and field in row:
                record[field] = row[field]
        record["anime"] = (
            f"{branch_name} 第{index + 1}期"
            if len(branch_names) == 1 and expansion_count > 1
            else branch_name
        )
        for field, lines in details.items():
            record[field] = lines[index]
        record["entry"] = (
            row.get("main_entry")
            or row.get("entry")
            or ""
        )
        record["sequel"] = row_is_red
        records.append(record)
    return records


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "TRUE" if value else "FALSE"
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value)
    return "\n".join(
        line.strip()
        for line in text.replace("\t", "").splitlines()
        if line.strip()
    ).strip()


def _value_at(values: list[str], index: int) -> str:
    return values[index] if index < len(values) else ""


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _is_openpyxl_red(color: Any) -> bool:
    if color is None:
        return False
    if color.type == "rgb" and color.rgb:
        return _is_red_hex(color.rgb)
    if color.type == "indexed" and color.indexed is not None:
        from openpyxl.styles.colors import COLOR_INDEX

        if color.indexed < len(COLOR_INDEX):
            return _is_red_hex(COLOR_INDEX[color.indexed])
    return False


def _is_red_hex(value: str) -> bool:
    value = value[-6:]
    try:
        red, green, blue = (
            int(value[offset : offset + 2], 16)
            for offset in (0, 2, 4)
        )
    except ValueError:
        return False
    return red >= 180 and green <= 80 and blue <= 80


def _is_xlrd_red(
    workbook: Any,
    worksheet: Any,
    row: int,
    column: int,
) -> bool:
    cell = worksheet.cell(row, column)
    xf = workbook.xf_list[cell.xf_index]
    font = workbook.font_list[xf.font_index]
    color = workbook.colour_map.get(font.colour_index)
    return (
        color is not None
        and color[0] >= 180
        and color[1] <= 80
        and color[2] <= 80
    )
