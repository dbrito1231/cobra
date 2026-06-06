"""Communication built-in tool."""

from __future__ import annotations

from tools.models import ToolCall
from tools.privacy import enforce_draft_local_only


def handle(call: ToolCall) -> dict:
    enforce_draft_local_only(call)
    return {
        "status": "draft_only",
        "platform": call.params.get("platform"),
        "recipient": call.params.get("recipient"),
        "subject": call.params.get("subject"),
        "draft": call.params.get("draft") or call.params.get("body") or "",
        "message": "Draft prepared locally. No message was sent.",
    }
