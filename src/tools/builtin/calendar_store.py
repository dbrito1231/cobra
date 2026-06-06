"""Local calendar persistence under ~/.cobra/calendar/."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_STORE_LOCK = threading.Lock()


def calendar_dir() -> Path:
    return Path.home() / ".cobra" / "calendar"


def events_path() -> Path:
    return calendar_dir() / "events.json"


def _empty_store() -> dict[str, Any]:
    return {"events": []}


def _load_store() -> dict[str, Any]:
    path = events_path()
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store()
    if not isinstance(data.get("events"), list):
        return _empty_store()
    return data


def _save_store(data: dict[str, Any]) -> None:
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            from dateutil import parser as dateutil_parser

            parsed = dateutil_parser.parse(str(value))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_end(event: dict[str, Any]) -> datetime | None:
    ends_at = parse_datetime(event.get("ends_at"))
    if ends_at:
        return ends_at
    starts_at = parse_datetime(event.get("starts_at"))
    duration = event.get("duration_minutes")
    if starts_at and duration is not None:
        return starts_at + timedelta(minutes=int(duration))
    return starts_at


def _serialize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "title": event.get("title", ""),
        "starts_at": event.get("starts_at"),
        "ends_at": event.get("ends_at"),
        "duration_minutes": event.get("duration_minutes"),
        "description": event.get("description", ""),
        "created_at": event.get("created_at"),
        "updated_at": event.get("updated_at"),
    }


def list_events(
    *,
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
) -> list[dict[str, Any]]:
    with _STORE_LOCK:
        events = [_serialize_event(item) for item in _load_store()["events"]]

    filtered: list[dict[str, Any]] = []
    for event in events:
        start = parse_datetime(event.get("starts_at"))
        if starts_after and start and start < starts_after:
            continue
        if starts_before and start and start > starts_before:
            continue
        filtered.append(event)
    filtered.sort(key=lambda item: item.get("starts_at") or "")
    return filtered


def check_schedule(*, on_date: datetime | None = None) -> dict[str, Any]:
    day = (on_date or datetime.now(timezone.utc)).astimezone(timezone.utc)
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    events = list_events(starts_after=day_start, starts_before=day_end)
    return {
        "date": day_start.date().isoformat(),
        "event_count": len(events),
        "events": events,
    }


def create_event(params: dict[str, Any]) -> dict[str, Any]:
    title = str(params.get("title") or "").strip()
    if not title:
        raise ValueError("calendar create requires a title.")

    starts_at = parse_datetime(params.get("starts_at"))
    if starts_at is None:
        raise ValueError("calendar create requires starts_at.")

    duration_minutes = params.get("duration_minutes")
    ends_at = parse_datetime(params.get("ends_at"))
    if ends_at is None and duration_minutes is not None:
        ends_at = starts_at + timedelta(minutes=int(duration_minutes))

    now = datetime.now(timezone.utc).isoformat()
    event = {
        "id": str(uuid4()),
        "title": title,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat() if ends_at else None,
        "duration_minutes": int(duration_minutes) if duration_minutes is not None else None,
        "description": str(params.get("description") or ""),
        "created_at": now,
        "updated_at": now,
    }

    with _STORE_LOCK:
        store = _load_store()
        store["events"].append(event)
        _save_store(store)

    return _serialize_event(event)


def update_event(event_id: str, params: dict[str, Any]) -> dict[str, Any]:
    with _STORE_LOCK:
        store = _load_store()
        for index, event in enumerate(store["events"]):
            if event.get("id") != event_id:
                continue
            if "title" in params and params["title"] is not None:
                event["title"] = str(params["title"]).strip()
            if params.get("starts_at") is not None:
                parsed = parse_datetime(params.get("starts_at"))
                if parsed is None:
                    raise ValueError("starts_at must be a valid datetime.")
                event["starts_at"] = parsed.isoformat()
            if params.get("ends_at") is not None:
                parsed = parse_datetime(params.get("ends_at"))
                event["ends_at"] = parsed.isoformat() if parsed else None
            if params.get("duration_minutes") is not None:
                event["duration_minutes"] = int(params["duration_minutes"])
            if "description" in params and params["description"] is not None:
                event["description"] = str(params["description"])
            event["updated_at"] = datetime.now(timezone.utc).isoformat()
            store["events"][index] = event
            _save_store(store)
            return _serialize_event(event)
    raise ValueError(f"Unknown calendar event: {event_id}")


def delete_event(event_id: str) -> dict[str, Any]:
    with _STORE_LOCK:
        store = _load_store()
        remaining = [event for event in store["events"] if event.get("id") != event_id]
        if len(remaining) == len(store["events"]):
            raise ValueError(f"Unknown calendar event: {event_id}")
        deleted = next(event for event in store["events"] if event.get("id") == event_id)
        store["events"] = remaining
        _save_store(store)
        return _serialize_event(deleted)
