"""交互事件坐标辅助。"""

from __future__ import annotations


def is_hover(event) -> bool:
    return (
        event.data is True
        or str(event.data).lower() == "true"
    )


def event_position(event) -> tuple[float, float]:
    position = getattr(event, "global_position", None)
    if position is None:
        position = getattr(event, "local_position", None)
    if position is None:
        return 0.0, 0.0
    return float(position.x), float(position.y)
