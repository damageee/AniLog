"""自动填表的进度 ticker。"""

from __future__ import annotations

import asyncio
import time


async def ticker(owner, state, elapsed_label) -> None:
    while owner._fill_running and not state["shown"]:
        await asyncio.sleep(1.0)
        if state["shown"]:
            break
        elapsed_label.value = (
            f"{int(round(time.monotonic() - float(state['start'])))}s"
        )
        try:
            elapsed_label.update()
        except Exception:
            pass
