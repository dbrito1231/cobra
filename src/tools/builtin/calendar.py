"""Calendar built-in tool — local schedule at ~/.cobra/calendar/."""

from __future__ import annotations

from tools.builtin.calendar_store import (
    check_schedule,
    create_event,
    delete_event,
    list_events,
    parse_datetime,
    update_event,
)
from tools.models import ToolCall


def _operation_for(call: ToolCall) -> str:
    if call.tool_name == "calendar_read":
        return "read"
    if call.tool_name == "calendar_write":
        return "create"
    return str(call.params.get("operation", "read")).lower()


def handle(call: ToolCall) -> dict:
    operation = _operation_for(call)

    if operation in {"read", "list"}:
        starts_after = parse_datetime(call.params.get("starts_after"))
        starts_before = parse_datetime(call.params.get("starts_before"))
        events = list_events(starts_after=starts_after, starts_before=starts_before)
        return {
            "operation": operation,
            "status": "ok",
            "event_count": len(events),
            "events": events,
        }

    if operation in {"check", "schedule"}:
        on_date = parse_datetime(call.params.get("date") or call.params.get("on_date"))
        schedule = check_schedule(on_date=on_date)
        return {"operation": "check", "status": "ok", **schedule}

    if operation == "create":
        event = create_event(call.params)
        return {"operation": "create", "status": "created", "event": event}

    if operation == "update":
        event_id = str(call.params.get("event_id") or call.params.get("id") or "").strip()
        if not event_id:
            raise ValueError("calendar update requires event_id.")
        event = update_event(event_id, call.params)
        return {"operation": "update", "status": "updated", "event": event}

    if operation == "delete":
        event_id = str(call.params.get("event_id") or call.params.get("id") or "").strip()
        if not event_id:
            raise ValueError("calendar delete requires event_id.")
        event = delete_event(event_id)
        return {"operation": "delete", "status": "deleted", "event": event}

    raise NotImplementedError(f"Unsupported calendar operation: {operation}")
