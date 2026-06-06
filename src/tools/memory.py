"""Local-only tool memory logging to wiki and JSONL backup."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from tools.models import ToolResult
from tools.privacy import local_tool_log_path, wiki_tool_log_path


_LOG_LOCK = threading.Lock()
_WIKI_HEADER = "# Tools Log\n\nEvery tool invocation is recorded locally (TM1–TM4).\n"


def _wiki_entry(result: ToolResult) -> str:
    """Format TM1–TM4 fields for the wiki Tools log page."""

    call = result.tool_call
    action = str(call.params.get("operation") or call.params.get("action") or "invoke")
    outcome = "success" if result.success else f"failure: {result.error or 'unknown'}"
    timestamp = result.timestamp.astimezone(timezone.utc).isoformat()
    return (
        f"\n## {timestamp}\n"
        f"- **Tool (TM1):** {call.tool_name}\n"
        f"- **Action (TM2):** {action}\n"
        f"- **Outcome (TM3):** {outcome}\n"
        f"- **Timestamp (TM4):** {timestamp}\n"
    )


def _append_wiki_entry(result: ToolResult) -> None:
    path = wiki_tool_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_WIKI_HEADER, encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_wiki_entry(result))


def _append_jsonl_entry(result: ToolResult) -> None:
    path = local_tool_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.to_dict(), default=str) + "\n")


def log_tool_result(result: ToolResult) -> None:
    """LOG: append wiki entry (primary) and JSONL backup for completed tool calls."""

    with _LOG_LOCK:
        _append_wiki_entry(result)
        _append_jsonl_entry(result)
