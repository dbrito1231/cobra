"""Phase 6 stub: user-defined tool design and registration."""

from __future__ import annotations

from tools.models import ToolCall


def propose_tool_design(description: str) -> dict:
    """Node E3 placeholder: produce a reviewable design before building."""

    return {
        "description": description,
        "status": "design_required",
        "message": "Custom tool registry format is deferred to Phase 6.",
    }


def handle(call: ToolCall) -> dict:
    """Registered extensibility tool handler placeholder."""

    description = str(call.params.get("description", ""))
    return propose_tool_design(description)
