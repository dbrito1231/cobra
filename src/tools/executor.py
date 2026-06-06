"""Public execution spine for the C.O.B.R.A. tools component."""

from __future__ import annotations

import asyncio
import dataclasses
import threading
from datetime import datetime, timedelta, timezone

from tools.approval import (
    denied_result,
    draft_communication,
    execute_approved,
    execute_read_only,
    request_code_approval,
    request_destructive_approval,
)
from tools.chaining import ToolChain, should_continue_chain
from tools.memory import log_tool_result
from tools.models import ActionType, ApprovalEvent, FailureEvent, ToolCall, ToolResult
from tools.router import route_action_type


PENDING_EVENT_TTL = timedelta(hours=24)

_PENDING_APPROVALS: dict[str, ApprovalEvent] = {}
_PENDING_FAILURES: dict[str, FailureEvent] = {}
_PAUSED_CHAINS: dict[str, ToolChain] = {}
_APPROVAL_CHAIN_MAP: dict[str, str] = {}
_FAILURE_CHAIN_MAP: dict[str, str] = {}
_STATE_LOCK = threading.RLock()


async def _run_blocking(function, *args):
    return await asyncio.to_thread(function, *args)


def _finalize_result(result: ToolResult) -> ToolResult:
    """LOG -> U: persist local tool memory before returning to the brain (sync helper)."""

    try:
        log_tool_result(result)
    except OSError as exc:
        result.notifications.append(f"Tool memory logging failed: {exc}")
    return result


async def _finalize(result: ToolResult) -> ToolResult:
    """Async wrapper: offloads file I/O in _finalize_result to a thread."""

    return await asyncio.to_thread(_finalize_result, result)


def _unknown_approval_result(event_id: str) -> ToolResult:
    return ToolResult(
        success=False,
        output=f"Approval '{event_id}' is unknown or expired. Nothing was executed.",
        tool_call=ToolCall(tool_name="unknown", params={"event_id": event_id}),
        error="unknown_or_expired_approval",
    )


def _is_expired(event: ApprovalEvent | FailureEvent) -> bool:
    return datetime.now(timezone.utc) - event.created_at > PENDING_EVENT_TTL


def _prune_expired_approvals() -> None:
    expired_ids = [event_id for event_id, event in _PENDING_APPROVALS.items() if _is_expired(event)]
    for event_id in expired_ids:
        _PENDING_APPROVALS.pop(event_id, None)
        _APPROVAL_CHAIN_MAP.pop(event_id, None)


def _prune_expired_failures() -> None:
    expired_ids = [event_id for event_id, event in _PENDING_FAILURES.items() if _is_expired(event)]
    for event_id in expired_ids:
        _PENDING_FAILURES.pop(event_id, None)
        _FAILURE_CHAIN_MAP.pop(event_id, None)


def _store_approval_locked(event: ApprovalEvent) -> None:
    with _STATE_LOCK:
        _prune_expired_approvals()
        _PENDING_APPROVALS[event.event_id] = event
        if event.chain_id:
            _APPROVAL_CHAIN_MAP[event.event_id] = event.chain_id


def _store_failure_locked(event: FailureEvent) -> None:
    with _STATE_LOCK:
        _prune_expired_failures()
        _PENDING_FAILURES[event.event_id] = event
        if event.chain_id:
            _FAILURE_CHAIN_MAP[event.event_id] = event.chain_id


def _pop_approval_locked(event_id: str) -> tuple[ApprovalEvent | None, str | None]:
    with _STATE_LOCK:
        _prune_expired_approvals()
        event = _PENDING_APPROVALS.pop(event_id, None)
        if event is None:
            return None, None
        mapped_chain_id = _APPROVAL_CHAIN_MAP.pop(event_id, None)
        if _is_expired(event):
            # Clean up any chain that was waiting on this approval.
            if mapped_chain_id:
                _PAUSED_CHAINS.pop(mapped_chain_id, None)
            return None, None
        return event, mapped_chain_id


def _remove_paused_chain_locked(chain_id: str | None) -> None:
    if not chain_id:
        return
    with _STATE_LOCK:
        _PAUSED_CHAINS.pop(chain_id, None)


def _pop_paused_chain_locked(chain_id: str | None) -> ToolChain | None:
    if not chain_id:
        return None
    with _STATE_LOCK:
        return _PAUSED_CHAINS.pop(chain_id, None)


def _pop_failure_locked(event_id: str) -> tuple[FailureEvent | None, str | None]:
    with _STATE_LOCK:
        event = _PENDING_FAILURES.pop(event_id, None)
        linked_chain_id = _FAILURE_CHAIN_MAP.pop(event_id, None)
        return event, linked_chain_id


def _pause_chain_for_approval_locked(chain: ToolChain, outcome: ApprovalEvent) -> None:
    with _STATE_LOCK:
        _PAUSED_CHAINS[chain.chain_id] = chain
        _APPROVAL_CHAIN_MAP[outcome.event_id] = chain.chain_id


def _pause_chain_for_failure_locked(chain: ToolChain) -> None:
    with _STATE_LOCK:
        _PAUSED_CHAINS[chain.chain_id] = chain


def _register_paused_chain_locked(chain: ToolChain) -> None:
    with _STATE_LOCK:
        _PAUSED_CHAINS[chain.chain_id] = chain


def _cleanup_paused_chain_locked(
    chain_id: str,
    outcome: ToolResult | ApprovalEvent | FailureEvent,
) -> None:
    with _STATE_LOCK:
        if chain_id in _PAUSED_CHAINS and not isinstance(outcome, (ApprovalEvent, FailureEvent)):
            _PAUSED_CHAINS.pop(chain_id, None)


async def _store_approval(event: ApprovalEvent) -> None:
    await asyncio.to_thread(_store_approval_locked, event)


async def _store_failure(event: FailureEvent) -> None:
    await asyncio.to_thread(_store_failure_locked, event)


async def _pop_approval(event_id: str) -> tuple[ApprovalEvent | None, str | None]:
    return await asyncio.to_thread(_pop_approval_locked, event_id)


async def _remove_paused_chain(chain_id: str | None) -> None:
    await asyncio.to_thread(_remove_paused_chain_locked, chain_id)


async def _pop_paused_chain(chain_id: str | None) -> ToolChain | None:
    return await asyncio.to_thread(_pop_paused_chain_locked, chain_id)


def _attach_chain_id(call: ToolCall, chain_id: str | None) -> ToolCall:
    if chain_id and call.chain_id is None:
        return dataclasses.replace(call, chain_id=chain_id)
    return call


async def _dispatch_call(call: ToolCall) -> ToolResult | ApprovalEvent | FailureEvent:
    action_type = route_action_type(call)

    if action_type is ActionType.READ_ONLY:
        outcome = await _run_blocking(execute_read_only, call)
        if isinstance(outcome, FailureEvent):
            await _store_failure(outcome)
            return outcome
        return await _finalize(outcome)

    if action_type is ActionType.DESTRUCTIVE:
        event = request_destructive_approval(call)
        await _store_approval(event)
        return event

    if action_type is ActionType.CODE_EXECUTION:
        event = request_code_approval(call)
        await _store_approval(event)
        return event

    if action_type is ActionType.COMMUNICATION:
        outcome = draft_communication(call)
        if isinstance(outcome, ToolResult):
            return await _finalize(outcome)
        await _store_approval(outcome)
        return outcome

    raise ValueError(f"Unhandled action type: {action_type}")


async def execute_tool(call: ToolCall) -> ToolResult | ApprovalEvent | FailureEvent:
    """
    Node A -> B -> approval paths -> G -> L/M/N -> O -> SUCCESS/DENIED.

    Returns ToolResult on immediate completion, ApprovalEvent when user input
    is required, or FailureEvent when retries are exhausted.
    """

    return await _dispatch_call(call)


async def resolve_approval(
    event_id: str,
    approved: bool,
    chain_id: str | None = None,
) -> ToolResult | ApprovalEvent | FailureEvent:
    """Resolve an approval card response from the brain pipeline or Chat UI."""

    event, mapped_chain_id = await _pop_approval(event_id)
    if event is None:
        return _unknown_approval_result(event_id)

    linked_chain_id = chain_id or mapped_chain_id

    if not approved:
        result = await _finalize(denied_result(event.tool_call))
        await _remove_paused_chain(linked_chain_id)
        return result

    if event.action_type is ActionType.COMMUNICATION:
        result = await _finalize(
            ToolResult(
                success=True,
                output={
                    "message": "Draft prepared for manual sending. No message was sent.",
                    "draft": event.draft_content,
                },
                tool_call=event.tool_call,
            )
        )
        chain = await _pop_paused_chain(linked_chain_id)
        if chain is not None:
            chain.results.append(result)
            chain.advance()
            return await _continue_chain(chain)
        return result

    outcome = await _run_blocking(execute_approved, event.tool_call)
    if isinstance(outcome, FailureEvent):
        await _store_failure(outcome)
        await _remove_paused_chain(linked_chain_id)
        return outcome

    result = await _finalize(outcome)
    chain = await _pop_paused_chain(linked_chain_id)
    if chain is not None:
        chain.results.append(result)
        chain.advance()
        return await _continue_chain(chain)
    return result


async def resolve_failure(event_id: str, continue_chain: bool = False) -> ToolResult | ApprovalEvent | FailureEvent:
    """Resolve a failure event after the user decides how to proceed."""

    event, linked_chain_id = await asyncio.to_thread(_pop_failure_locked, event_id)

    if event is None:
        return ToolResult(
            success=False,
            output=f"Failure event '{event_id}' is unknown or already resolved.",
            tool_call=ToolCall(tool_name="unknown", params={"event_id": event_id}),
            error="unknown_failure_event",
        )

    if continue_chain and linked_chain_id:
        chain = await _pop_paused_chain(linked_chain_id)
        if chain is not None:
            chain.advance()
            return await _continue_chain(chain)

    await _remove_paused_chain(linked_chain_id)

    return await _finalize(event.last_result)


async def _continue_chain(chain: ToolChain) -> ToolResult | ApprovalEvent | FailureEvent:
    while should_continue_chain(chain):
        call = chain.peek_next()
        if call is None:
            break

        _attach_chain_id(call, chain.chain_id)
        outcome = await _dispatch_call(call)

        if isinstance(outcome, ApprovalEvent):
            await asyncio.to_thread(_pause_chain_for_approval_locked, chain, outcome)
            return outcome

        if isinstance(outcome, FailureEvent):
            await asyncio.to_thread(_pause_chain_for_failure_locked, chain)
            return outcome

        if not outcome.success:
            return await _finalize(outcome)

        chain.results.append(outcome)
        chain.advance()

    if not chain.results:
        return await _finalize(
            ToolResult(
                success=False,
                output="Tool chain completed without results.",
                tool_call=ToolCall(tool_name="tool_chain", params={"chain_id": chain.chain_id}),
                error="empty_chain",
            )
        )

    return chain.results[-1]


async def execute_chain(chain: ToolChain) -> ToolResult | ApprovalEvent | FailureEvent:
    """Execute a multi-tool chain with pause/resume on approval or failure."""

    await asyncio.to_thread(_register_paused_chain_locked, chain)

    outcome = await _continue_chain(chain)

    await asyncio.to_thread(_cleanup_paused_chain_locked, chain.chain_id, outcome)

    return outcome


def pending_approvals() -> tuple[ApprovalEvent, ...]:
    """Expose current pending approvals for orchestration and tests."""

    with _STATE_LOCK:
        _prune_expired_approvals()
        return tuple(_PENDING_APPROVALS.values())


def pending_failures() -> tuple[FailureEvent, ...]:
    """Expose current pending failure events."""

    with _STATE_LOCK:
        _prune_expired_failures()
        return tuple(_PENDING_FAILURES.values())


def prune_expired_approvals() -> int:
    """Remove expired pending approvals; returns count removed."""

    with _STATE_LOCK:
        before = len(_PENDING_APPROVALS)
        _prune_expired_approvals()
        return before - len(_PENDING_APPROVALS)


def prune_expired_failures() -> int:
    """Remove expired pending failure events; returns count removed."""

    with _STATE_LOCK:
        before = len(_PENDING_FAILURES)
        _prune_expired_failures()
        return before - len(_PENDING_FAILURES)
