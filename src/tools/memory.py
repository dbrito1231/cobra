"""Local-only tool memory logging."""

from __future__ import annotations

import json
import threading

from tools.models import ToolResult
from tools.privacy import local_tool_log_path


_LOG_LOCK = threading.Lock()


def log_tool_result(result: ToolResult) -> None:
    """LOG: append a local JSONL entry for completed tool calls."""

    path = local_tool_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.to_dict(), default=str) + "\n")
