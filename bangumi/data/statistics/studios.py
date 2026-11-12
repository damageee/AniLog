"""制作公司统计。"""

from __future__ import annotations

from bangumi.data.watched_data import Record, split_studios


def studio_statistics(
    records: list[Record],
) -> list[tuple[str, int, list[Record]]]:
    """按数量降序返回 ``(studio, record_rows, records)``。

    每个列出该公司的表格行计一次；条目和动画名不去重。
    """
    groups: dict[str, list[Record]] = {}
    for record in records:
        for studio in split_studios(record.get("studio")):
            groups.setdefault(studio, []).append(record)
    items = [
        (studio, len(company_records), company_records)
        for studio, company_records in groups.items()
    ]
    items.sort(key=lambda item: (-item[1], item[0]))
    return items
