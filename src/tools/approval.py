"""Approval model paths for tool execution."""

from __future__ import annotations

from tools.failure import run_tool_with_retry
from tools.models import ActionType, ApprovalEvent, FailureEvent, ToolCall, ToolResult
from tools.privacy import communication_send_attempted, sanitize_tool_call


def execute_read_only(call: ToolCall) -> ToolResult | FailureEvent:
    """Node C: read-only tools execute automatically."""

    return run_tool_with_retry(sanitize_tool_call(call))


def request_destructive_approval(call: ToolCall) -> ApprovalEvent:
    """Nodes E/F: explain the destructive action and wait for approval."""

    operation = call.params.get("operation", "execute")
    explanation = (
        f"C.O.B.R.A. wants to run '{call.tool_name}' with operation '{operation}'. "
        "This may modify, delete, create, or otherwise change local state."
    )
    return ApprovalEvent(
        action_type=ActionType.DESTRUCTIVE,
        explanation=explanation,
        tool_call=call,
        chain_id=call.chain_id,
    )


def request_code_approval(call: ToolCall) -> ApprovalEvent:
    """Nodes H/I: always show generated code before execution."""

    code = str(call.params.get("code", ""))
    explanation = "C.O.B.R.A. wants to run code. Review and approve before execution."
    return ApprovalEvent(
        action_type=ActionType.CODE_EXECUTION,
        explanation=explanation,
        tool_call=call,
        code_preview=code,
        chain_id=call.chain_id,
    )


def draft_communication(call: ToolCall) -> ApprovalEvent | ToolResult:
    """Nodes J/K: communication tools produce drafts only and never send."""

    if communication_send_attempted(call):
        return send_denied_result(call)

    draft = str(call.params.get("draft") or call.params.get("body") or "")
    recipient = call.params.get("recipient")
    if recipient:
        draft = f"To: {recipient}\n\n{draft}"

    return ApprovalEvent(
        action_type=ActionType.COMMUNICATION,
        explanation="Communication tools create local drafts only. No message was sent.",
        tool_call=call,
        draft_content=draft,
        chain_id=call.chain_id,
    )


def execute_approved(call: ToolCall) -> ToolResult | FailureEvent:
    """Node G: execute a previously approved call."""

    return run_tool_with_retry(sanitize_tool_call(call))


def denied_result(call: ToolCall, error: str = "denied", message: str | None = None) -> ToolResult:
    """DENIED: user declined approval or action was blocked; nothing executes."""

    return ToolResult(
        success=False,
        output=message or "Action cancelled by user. Nothing was executed.",
        tool_call=call,
        error=error,
    )


def send_denied_result(call: ToolCall) -> ToolResult:
    """Blocked communication send attempt."""

    return denied_result(
        call,
        error="send_not_allowed",
        message="Communication tools are draft-only; sending is not allowed.",
    )
