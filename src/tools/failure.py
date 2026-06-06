"""Retry and user escalation rules for tool execution failures."""

from __future__ import annotations

from tools.models import FailureEvent, ToolCall, ToolResult
from tools.sandbox import run_tool


MAX_RETRIES = 1


def should_retry(result: ToolResult, attempts: int) -> bool:
    """Node P/Q: retry once before escalating to the user."""

    return not result.success and attempts < MAX_RETRIES


def escalation_message(call: ToolCall, result: ToolResult) -> str:
    """Node R: explain the persistent failure."""

    return (
        f"Tool '{call.tool_name}' failed after retry policy was exhausted. "
        f"Error: {result.error or result.output}"
    )


def make_failure_event(call: ToolCall, result: ToolResult) -> FailureEvent:
    """Build a failure event for node S user recovery."""

    return FailureEvent(
        tool_call=call,
        message=escalation_message(call, result),
        last_result=result,
        chain_id=call.chain_id,
    )


def run_tool_with_retry(call: ToolCall) -> ToolResult | FailureEvent:
    """Execute a tool with one automatic retry before escalation."""

    first_result = run_tool(call)
    if first_result.success:
        return first_result

    retry_result = run_tool(call)
    if retry_result.success:
        return retry_result

    return make_failure_event(call, retry_result)
