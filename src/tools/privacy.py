"""Privacy gates for outbound tool calls, drafts, and logs."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from tools.models import ToolCall


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
HOME_PATH_RE = re.compile(r"/Users/[^/\s]+")

SEND_ACTIONS = {"send", "deliver", "post", "publish"}


def sanitize_text(value: str) -> str:
    """Best-effort removal of personal context from outbound strings."""

    sanitized = EMAIL_RE.sub("[email]", value)
    sanitized = PHONE_RE.sub("[phone]", sanitized)
    sanitized = HOME_PATH_RE.sub("[home]", sanitized)
    return sanitized.strip()


def sanitize_outbound_params(params: dict[str, Any]) -> dict[str, Any]:
    """PR1: outbound calls get topic-level parameters, not personal context."""

    sanitized: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_text(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_text(item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, dict):
            sanitized[key] = sanitize_outbound_params(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_tool_call(call: ToolCall) -> ToolCall:
    """Return a sanitized copy of a tool call before outbound execution."""

    return replace(call, params=sanitize_outbound_params(call.params))


def communication_send_attempted(call: ToolCall) -> bool:
    """Return True when a communication call attempts to send instead of draft."""

    action = str(call.params.get("action") or call.params.get("operation") or "draft").lower()
    return action in SEND_ACTIONS


def enforce_draft_local_only(call: ToolCall) -> None:
    """PR2: communication tools are draft-only and must not send messages."""

    if communication_send_attempted(call):
        raise ValueError("Communication tools are draft-only; sending is not allowed.")


def local_tool_log_path() -> Path:
    """PR3: tool logs are local-only under the user's C.O.B.R.A. directory."""

    return Path.home() / ".cobra" / "tools-log.jsonl"
