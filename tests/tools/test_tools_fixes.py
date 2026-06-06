from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools import (
    ToolCall,
    ToolChain,
    execute_chain,
    execute_tool,
    pending_approvals,
    pending_failures,
    prune_expired_failures,
    resolve_approval,
    resolve_failure,
)
from tools.executor import (
    _APPROVAL_CHAIN_MAP,
    _FAILURE_CHAIN_MAP,
    _PENDING_APPROVALS,
    _PENDING_FAILURES,
    _PAUSED_CHAINS,
    _pop_approval,
    _store_approval,
    PENDING_EVENT_TTL,
)
from tools.models import ActionType, ApprovalEvent, FailureEvent, ToolResult
from tools.sandbox import run_sandboxed


@pytest.fixture(autouse=True)
def clear_executor_state():
    _PENDING_APPROVALS.clear()
    _PENDING_FAILURES.clear()
    _PAUSED_CHAINS.clear()
    _APPROVAL_CHAIN_MAP.clear()
    _FAILURE_CHAIN_MAP.clear()
    yield
    _PENDING_APPROVALS.clear()
    _PENDING_FAILURES.clear()
    _PAUSED_CHAINS.clear()
    _APPROVAL_CHAIN_MAP.clear()
    _FAILURE_CHAIN_MAP.clear()


@pytest.mark.asyncio
async def test_resolve_approval_unknown_id():
    result = await resolve_approval("missing-event", approved=True)
    assert result.success is False
    assert result.error == "unknown_or_expired_approval"


@pytest.mark.asyncio
async def test_sandbox_timeout_returns_failure():
    call = ToolCall("file_management", {"operation": "exists", "path": "Welcome.md", "timeout_seconds": 1})
    with patch("tools.sandbox.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("cmd", 1)):
        result = run_sandboxed(call)
    assert result.success is False
    assert result.error == "timeout"


@pytest.mark.asyncio
async def test_sandbox_malformed_json():
    call = ToolCall("file_management", {"operation": "exists", "path": "Welcome.md"})
    mock_process = MagicMock()
    mock_process.stdout = "not-json"
    mock_process.stderr = ""
    mock_process.returncode = 1
    with patch("tools.sandbox.subprocess.run", return_value=mock_process):
        result = run_sandboxed(call)
    assert result.success is False
    assert result.error == "sandbox_worker_output_parse_error"


@pytest.mark.asyncio
async def test_file_organize_moves_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "inbox"
    source.mkdir()
    (source / "note.md").write_text("hello", encoding="utf-8")
    (source / "ignore.txt").write_text("skip", encoding="utf-8")

    call = ToolCall(
        "file_management",
        {
            "operation": "organize",
            "path": str(source),
            "rules": {".md": "docs"},
        },
        sandboxed=False,
    )
    from tools.builtin.file_management import handle

    result = handle(call)
    assert len(result["moved"]) == 1
    assert (source / "docs" / "note.md").exists()
    assert len(result["skipped"]) == 1


@pytest.mark.asyncio
async def test_retry_once_then_failure_event():
    call = ToolCall("app_control", {"operation": "open"}, sandboxed=False)

    failing = ToolResult(success=False, output=None, tool_call=call, error="boom")

    with patch("tools.failure.run_tool", side_effect=[failing, failing]):
        from tools.failure import run_tool_with_retry

        outcome = run_tool_with_retry(call)

    assert isinstance(outcome, FailureEvent)
    assert "failed after retry policy was exhausted" in outcome.message


@pytest.mark.asyncio
async def test_communication_send_returns_denied():
    call = ToolCall("communication", {"action": "send", "body": "hello"})
    result = await execute_tool(call)
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error == "send_not_allowed"


@pytest.mark.asyncio
async def test_execute_chain_read_only_sequence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("chain", encoding="utf-8")

    chain = ToolChain(
        chain_id="chain-1",
        calls=[
            ToolCall("file_management", {"operation": "exists", "path": str(target)}, sandboxed=False),
            ToolCall("system_control", {"operation": "status"}, sandboxed=False),
        ],
    )

    result = await execute_chain(chain)
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert len(chain.results) == 2


@pytest.mark.asyncio
async def test_pending_approvals_exported():
    call = ToolCall("file_write", {"operation": "write", "path": "x.txt", "content": "data"})
    event = await execute_tool(call)
    assert event.__class__.__name__ == "ApprovalEvent"
    assert len(pending_approvals()) == 1


@pytest.mark.asyncio
async def test_resolve_failure_unknown_event():
    result = await resolve_failure("missing-failure")
    assert result.success is False
    assert result.error == "unknown_failure_event"


@pytest.mark.asyncio
async def test_pop_approval_returns_chain_id_under_lock():
    call = ToolCall("file_write", {"operation": "write", "path": "x.txt"}, chain_id="chain-a")
    event = ApprovalEvent(
        action_type=ActionType.DESTRUCTIVE,
        explanation="test",
        tool_call=call,
        chain_id="chain-a",
    )
    await _store_approval(event)
    assert _APPROVAL_CHAIN_MAP[event.event_id] == "chain-a"

    popped_event, mapped_chain_id = await _pop_approval(event.event_id)
    assert popped_event is event
    assert mapped_chain_id == "chain-a"
    assert event.event_id not in _APPROVAL_CHAIN_MAP


@pytest.mark.asyncio
async def test_concurrent_resolve_approval_no_chain_map_corruption():
    chain1 = ToolChain(
        chain_id="chain-a",
        calls=[
            ToolCall(
                "file_write",
                {"operation": "write", "path": "a.txt", "content": "a"},
                chain_id="chain-a",
            ),
            ToolCall("system_control", {"operation": "status"}, chain_id="chain-a", sandboxed=False),
        ],
    )
    chain2 = ToolChain(
        chain_id="chain-b",
        calls=[
            ToolCall(
                "file_write",
                {"operation": "write", "path": "b.txt", "content": "b"},
                chain_id="chain-b",
            ),
            ToolCall("system_control", {"operation": "status"}, chain_id="chain-b", sandboxed=False),
        ],
    )

    event1 = await execute_chain(chain1)
    event2 = await execute_chain(chain2)
    assert isinstance(event1, ApprovalEvent)
    assert isinstance(event2, ApprovalEvent)

    def approved_result(call: ToolCall) -> ToolResult:
        return ToolResult(success=True, output="approved", tool_call=call)

    with patch("tools.executor.execute_approved", side_effect=approved_result):
        results = await asyncio.gather(
            resolve_approval(event1.event_id, approved=True),
            resolve_approval(event2.event_id, approved=True),
        )

    assert all(isinstance(result, ToolResult) and result.success for result in results)
    assert len(chain1.results) == 2
    assert len(chain2.results) == 2
    assert chain1.results[0].tool_call.params["path"] == "a.txt"
    assert chain2.results[0].tool_call.params["path"] == "b.txt"


@pytest.mark.asyncio
async def test_pending_failures_prunes_expired():
    call = ToolCall("app_control", {"operation": "open"})
    old_time = datetime.now(timezone.utc) - PENDING_EVENT_TTL - timedelta(hours=1)
    last_result = ToolResult(success=False, output=None, tool_call=call, error="boom")
    event = FailureEvent(
        tool_call=call,
        message="failed after retry policy was exhausted",
        last_result=last_result,
        created_at=old_time,
        chain_id="chain-x",
    )
    _PENDING_FAILURES[event.event_id] = event
    _FAILURE_CHAIN_MAP[event.event_id] = "chain-x"

    removed = prune_expired_failures()
    assert removed == 1
    assert len(pending_failures()) == 0
    assert event.event_id not in _FAILURE_CHAIN_MAP


@pytest.mark.asyncio
async def test_chain_failure_is_logged():
    chain = ToolChain(
        chain_id="chain-fail-log",
        calls=[
            ToolCall("system_control", {"operation": "status"}, sandboxed=False),
            ToolCall("communication", {"action": "send", "body": "hello"}),
        ],
    )

    with patch("tools.executor.log_tool_result") as mock_log:
        result = await execute_chain(chain)

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error == "send_not_allowed"
    mock_log.assert_any_call(result)


@pytest.mark.asyncio
async def test_concurrent_resolve_same_chain_no_paused_chains_corruption():
    chain = ToolChain(
        chain_id="chain-same",
        calls=[
            ToolCall(
                "file_write",
                {"operation": "write", "path": "same.txt", "content": "data"},
                chain_id="chain-same",
            ),
            ToolCall("system_control", {"operation": "status"}, chain_id="chain-same", sandboxed=False),
        ],
    )

    event = await execute_chain(chain)
    assert isinstance(event, ApprovalEvent)

    def approved_result(call: ToolCall) -> ToolResult:
        return ToolResult(success=True, output="approved", tool_call=call)

    with patch("tools.executor.execute_approved", side_effect=approved_result):
        results = await asyncio.gather(
            resolve_approval(event.event_id, approved=True),
            resolve_approval(event.event_id, approved=True),
        )

    outcomes = [result for result in results if isinstance(result, ToolResult)]
    assert len(outcomes) == 2
    assert sum(1 for result in outcomes if result.success) == 1
    assert sum(1 for result in outcomes if result.error == "unknown_or_expired_approval") == 1
    assert len(chain.results) == 2
    assert "chain-same" not in _PAUSED_CHAINS


@pytest.mark.asyncio
async def test_empty_chain_is_logged():
    chain = ToolChain(chain_id="chain-empty", calls=[])

    with patch("tools.executor.log_tool_result") as mock_log:
        result = await execute_chain(chain)

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error == "empty_chain"
    mock_log.assert_called_once()
    logged = mock_log.call_args[0][0]
    assert logged.error == "empty_chain"
