"""User-defined tool design and registration."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from tools.models import ActionType, ToolCall, ToolMeta
from tools.registry import TOOL_CATALOG, register_custom_handler

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_RESERVED_NAMES = frozenset({"extensibility"})


class ToolRegistrationError(ValueError):
    """Raised when a custom tool fails validation or conflicts with the catalog."""


def propose_tool_design(description: str) -> dict[str, Any]:
    """Node E3: produce a reviewable design before building."""

    return {
        "description": description,
        "status": "design_required",
        "proposed_name": _suggest_name(description),
        "message": "Review and approve the proposed tool design before registration.",
    }


def _suggest_name(description: str) -> str:
    words = re.findall(r"[a-z0-9]+", description.lower())
    if not words:
        return "custom_tool"
    return "_".join(words[:4])


def _coerce_action_type(value: ActionType | str) -> ActionType:
    if isinstance(value, ActionType):
        return value
    return ActionType(str(value))


def _coerce_operation_action_types(
    raw: dict[str, ActionType | str] | None,
) -> dict[str, ActionType]:
    if not raw:
        return {}
    return {operation: _coerce_action_type(action_type) for operation, action_type in raw.items()}


def register_tool(
    name: str,
    handler: Callable[[ToolCall], Any],
    metadata: dict[str, Any] | ToolMeta,
) -> ToolMeta:
    """Node E6: register a user-approved custom tool in the catalog."""

    normalized = name.strip().lower()
    if not _NAME_PATTERN.match(normalized):
        raise ToolRegistrationError(
            "Tool name must start with a letter and contain only lowercase letters, digits, or underscores."
        )
    if normalized in _RESERVED_NAMES:
        raise ToolRegistrationError(f"Tool name '{normalized}' is reserved.")
    if normalized in TOOL_CATALOG:
        raise ToolRegistrationError(f"Tool '{normalized}' is already registered.")
    if not callable(handler):
        raise ToolRegistrationError("Handler must be callable.")

    if isinstance(metadata, ToolMeta):
        meta = metadata
        if meta.name != normalized:
            raise ToolRegistrationError("ToolMeta.name must match the registered tool name.")
    else:
        if not metadata.get("description"):
            raise ToolRegistrationError("metadata must include a non-empty description.")
        meta = ToolMeta(
            name=normalized,
            description=str(metadata["description"]),
            action_type=_coerce_action_type(metadata.get("action_type", ActionType.DESTRUCTIVE)),
            handler=f"tools.extensibility.custom:{normalized}",
            default_operation=metadata.get("default_operation"),
            operation_action_types=_coerce_operation_action_types(
                metadata.get("operation_action_types")
            ),
        )

    TOOL_CATALOG[normalized] = meta
    register_custom_handler(normalized, handler)
    return meta


def handle(call: ToolCall) -> dict[str, Any]:
    """Registered extensibility tool handler."""

    description = str(call.params.get("description", ""))
    return propose_tool_design(description)
