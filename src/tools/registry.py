"""Built-in tool catalog and action-type classification."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tools.models import ActionType, ToolCall, ToolMeta


TOOL_CATALOG: dict[str, ToolMeta] = {
    "web_search": ToolMeta(
        name="web_search",
        description="Search the internet for information.",
        action_type=ActionType.READ_ONLY,
        handler="tools.builtin.web_search.handle",
    ),
    "code_execution": ToolMeta(
        name="code_execution",
        description="Write and run Python code after user approval.",
        action_type=ActionType.CODE_EXECUTION,
        handler="tools.builtin.code_execution.handle",
    ),
    "file_management": ToolMeta(
        name="file_management",
        description="Read, write, and organize files and folders.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.builtin.file_management.handle",
        default_operation="read",
        operation_action_types={
            "read": ActionType.READ_ONLY,
            "list": ActionType.READ_ONLY,
            "exists": ActionType.READ_ONLY,
            "write": ActionType.DESTRUCTIVE,
            "delete": ActionType.DESTRUCTIVE,
            "move": ActionType.DESTRUCTIVE,
            "copy": ActionType.DESTRUCTIVE,
            "mkdir": ActionType.DESTRUCTIVE,
            "organize": ActionType.DESTRUCTIVE,
        },
    ),
    "file_read": ToolMeta(
        name="file_read",
        description="Read a file.",
        action_type=ActionType.READ_ONLY,
        handler="tools.builtin.file_management.handle",
        default_operation="read",
    ),
    "file_write": ToolMeta(
        name="file_write",
        description="Write a file.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.builtin.file_management.handle",
        default_operation="write",
    ),
    "app_control": ToolMeta(
        name="app_control",
        description="Open, close, or interact with applications.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.builtin.app_control.handle",
        default_operation="open",
        operation_action_types={
            "list": ActionType.READ_ONLY,
            "open": ActionType.DESTRUCTIVE,
            "close": ActionType.DESTRUCTIVE,
            "activate": ActionType.DESTRUCTIVE,
            "focus": ActionType.DESTRUCTIVE,
            "interact": ActionType.DESTRUCTIVE,
        },
    ),
    "calendar": ToolMeta(
        name="calendar",
        description="Read or create calendar entries.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.builtin.calendar.handle",
        default_operation="read",
        operation_action_types={
            "read": ActionType.READ_ONLY,
            "check": ActionType.READ_ONLY,
            "list": ActionType.READ_ONLY,
            "create": ActionType.DESTRUCTIVE,
            "update": ActionType.DESTRUCTIVE,
            "delete": ActionType.DESTRUCTIVE,
        },
    ),
    "calendar_read": ToolMeta(
        name="calendar_read",
        description="Read calendar entries.",
        action_type=ActionType.READ_ONLY,
        handler="tools.builtin.calendar.handle",
        default_operation="read",
    ),
    "calendar_write": ToolMeta(
        name="calendar_write",
        description="Create or update calendar entries.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.builtin.calendar.handle",
        default_operation="create",
    ),
    "communication": ToolMeta(
        name="communication",
        description="Draft emails and messages. Never sends automatically.",
        action_type=ActionType.COMMUNICATION,
        handler="tools.builtin.communication.handle",
    ),
    "system_control": ToolMeta(
        name="system_control",
        description="Read or change system settings.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.builtin.system_control.handle",
        default_operation="status",
        operation_action_types={
            "status": ActionType.READ_ONLY,
            "read": ActionType.READ_ONLY,
            "wifi": ActionType.READ_ONLY,
            "volume": ActionType.DESTRUCTIVE,
            "brightness": ActionType.DESTRUCTIVE,
            "notifications": ActionType.DESTRUCTIVE,
            "settings": ActionType.DESTRUCTIVE,
        },
    ),
    "extensibility": ToolMeta(
        name="extensibility",
        description="Design and register user-defined tools after approval.",
        action_type=ActionType.DESTRUCTIVE,
        handler="tools.extensibility.handle",
    ),
}


CUSTOM_HANDLERS: dict[str, Callable[[ToolCall], Any]] = {}


class UnknownToolError(ValueError):
    """Raised when the brain requests a tool outside the catalog."""


def get_tool_meta(tool_name: str) -> ToolMeta:
    try:
        return TOOL_CATALOG[tool_name]
    except KeyError as exc:
        raise UnknownToolError(f"Unknown tool: {tool_name}") from exc


def register_custom_handler(name: str, handler: Callable[[ToolCall], Any]) -> None:
    """Store a callable handler for a registered custom tool."""

    CUSTOM_HANDLERS[name] = handler


def classify_tool_call(call: ToolCall) -> ActionType:
    """Resolve node B: classify a call by its tool and operation."""

    return get_tool_meta(call.tool_name).classify(call.params)
