"""Application control built-in tool."""

from __future__ import annotations

from tools.models import ToolCall


def handle(call: ToolCall) -> dict:
    return {
        "tool": call.tool_name,
        "operation": call.params.get("operation", "open"),
        "status": "not_implemented",
        "message": "App control adapters are deferred until the platform control API is chosen.",
    }
