"""Tests for custom tool registration."""

from __future__ import annotations

import pytest

from tools.extensibility import ToolRegistrationError, register_tool
from tools.models import ActionType, ToolCall
from tools.registry import CUSTOM_HANDLERS, TOOL_CATALOG, classify_tool_call, get_tool_meta
from tools.builtin import dispatch_builtin


@pytest.fixture(autouse=True)
def cleanup_custom_tools():
    snapshot = dict(TOOL_CATALOG)
    handlers = dict(CUSTOM_HANDLERS)
    yield
    TOOL_CATALOG.clear()
    TOOL_CATALOG.update(snapshot)
    CUSTOM_HANDLERS.clear()
    CUSTOM_HANDLERS.update(handlers)


def test_register_tool_adds_catalog_entry():
    def echo_handler(call: ToolCall) -> dict:
        return {"echo": call.params.get("text", "")}

    meta = register_tool(
        "echo_tool",
        echo_handler,
        {
            "description": "Echo text back to the caller.",
            "action_type": ActionType.READ_ONLY,
        },
    )

    assert meta.name == "echo_tool"
    assert get_tool_meta("echo_tool") is meta
    result = dispatch_builtin(ToolCall("echo_tool", {"text": "hello"}))
    assert result == {"echo": "hello"}


def test_register_tool_rejects_invalid_name():
    with pytest.raises(ToolRegistrationError):
        register_tool("Bad Name", lambda call: {}, {"description": "bad"})


def test_register_tool_rejects_duplicate_name():
    register_tool("dup_tool", lambda call: {}, {"description": "first"})
    with pytest.raises(ToolRegistrationError, match="already registered"):
        register_tool("dup_tool", lambda call: {}, {"description": "second"})


def test_register_tool_operation_action_types():
    register_tool(
        "flex_tool",
        lambda call: {"operation": call.params.get("operation")},
        {
            "description": "Flexible tool.",
            "action_type": ActionType.DESTRUCTIVE,
            "default_operation": "read",
            "operation_action_types": {
                "read": ActionType.READ_ONLY,
                "write": ActionType.DESTRUCTIVE,
            },
        },
    )
    read_call = ToolCall("flex_tool", {"operation": "read"})
    write_call = ToolCall("flex_tool", {"operation": "write"})
    assert classify_tool_call(read_call) is ActionType.READ_ONLY
    assert classify_tool_call(write_call) is ActionType.DESTRUCTIVE
