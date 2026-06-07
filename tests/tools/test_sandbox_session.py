"""Tests for session-scoped sandbox overrides."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.config import reset_session_sandbox, set_session_sandbox_override
from tools.models import ToolCall
from tools.sandbox import run_tool


@pytest.fixture(autouse=True)
def clear_session_sandbox():
    reset_session_sandbox()
    yield
    reset_session_sandbox()


def test_session_override_disables_sandbox():
    call = ToolCall("system_control", {"operation": "status"}, sandboxed=True)
    set_session_sandbox_override(False)

    with patch("tools.sandbox.run_unsandboxed") as mock_unsandboxed:
        mock_unsandboxed.return_value = MagicMock(success=True)
        run_tool(call)

    mock_unsandboxed.assert_called_once_with(call)


def test_session_override_enables_sandbox():
    call = ToolCall("system_control", {"operation": "status"}, sandboxed=False)
    set_session_sandbox_override(True)

    with patch("tools.sandbox.run_sandboxed") as mock_sandboxed:
        mock_sandboxed.return_value = MagicMock(success=True)
        run_tool(call)

    mock_sandboxed.assert_called_once_with(call)


def test_no_session_override_uses_call_flag():
    call = ToolCall("system_control", {"operation": "status"}, sandboxed=False)

    with patch("tools.sandbox.run_unsandboxed") as mock_unsandboxed:
        mock_unsandboxed.return_value = MagicMock(success=True)
        run_tool(call)

    mock_unsandboxed.assert_called_once_with(call)
