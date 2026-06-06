"""System control built-in tool."""

from __future__ import annotations

import platform

from tools.models import ToolCall


def handle(call: ToolCall) -> dict:
    operation = str(call.params.get("operation", "status")).lower()
    if operation in {"status", "read"}:
        return {
            "operation": operation,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        }

    return {
        "operation": operation,
        "status": "not_implemented",
        "message": "System setting changes are deferred until OS-specific adapters are chosen.",
    }
