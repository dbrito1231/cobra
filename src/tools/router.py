"""Action-type router for tool invocations."""

from __future__ import annotations

from tools.models import ActionType, ToolCall
from tools.registry import classify_tool_call


def route_action_type(call: ToolCall) -> ActionType:
    """Node B: decide which approval path a tool call must follow."""

    return classify_tool_call(call)
