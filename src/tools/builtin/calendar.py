"""Calendar built-in tool."""

from __future__ import annotations

from tools.models import ToolCall


def _operation_for(call: ToolCall) -> str:
    if call.tool_name == "calendar_read":
        return "read"
    if call.tool_name == "calendar_write":
        return "create"
    return str(call.params.get("operation", "read")).lower()


def handle(call: ToolCall) -> dict:
    operation = _operation_for(call)
    if operation in {"read", "check", "list"}:
        return {
            "operation": operation,
            "status": "not_configured",
            "events": [],
            "message": "Calendar read adapters are deferred until a local calendar source is chosen.",
        }

    if operation in {"create", "update", "delete"}:
        try:
            from dateutil import parser
        except ImportError:
            parser = None

        starts_at = call.params.get("starts_at")
        parsed_starts_at = parser.parse(str(starts_at)).isoformat() if starts_at and parser else starts_at
        return {
            "operation": operation,
            "status": "not_created",
            "event": {
                "title": call.params.get("title"),
                "starts_at": parsed_starts_at,
                "duration_minutes": call.params.get("duration_minutes"),
            },
            "message": "Calendar write adapters are deferred; no calendar event was created.",
        }

    raise NotImplementedError(f"Unsupported calendar operation: {operation}")
