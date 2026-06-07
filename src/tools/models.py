"""Shared data models for the C.O.B.R.A. tools component."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ActionType(str, Enum):
    """The approval class for a tool invocation."""

    READ_ONLY = "read_only"
    DESTRUCTIVE = "destructive"
    CODE_EXECUTION = "code_execution"
    COMMUNICATION = "communication"


@dataclass
class ToolCall:
    """A request from the brain pipeline to invoke a tool."""

    tool_name: str
    params: dict[str, Any] = field(default_factory=dict)
    sandboxed: bool = True
    chain_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        return cls(
            tool_name=data["tool_name"],
            params=dict(data.get("params") or {}),
            sandboxed=bool(data.get("sandboxed", True)),
            chain_id=data.get("chain_id"),
        )


@dataclass
class ToolResult:
    """The terminal result of a tool invocation."""

    success: bool
    output: Any
    tool_call: ToolCall
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    notifications: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class ApprovalEvent:
    """Emitted when user input is required before execution proceeds."""

    action_type: ActionType
    explanation: str
    tool_call: ToolCall
    event_id: str = field(default_factory=lambda: str(uuid4()))
    code_preview: str | None = None
    draft_content: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    chain_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action_type"] = self.action_type.value
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class FailureEvent:
    """Emitted when tool execution fails after retries; user decides next action."""

    tool_call: ToolCall
    message: str
    last_result: ToolResult
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    chain_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["last_result"] = self.last_result.to_dict()
        return data


@dataclass(frozen=True)
class ToolMeta:
    """Catalog metadata used to classify and dispatch a tool."""

    name: str
    description: str
    action_type: ActionType
    handler: str
    operation_action_types: dict[str, ActionType] = field(default_factory=dict)
    default_operation: str | None = None

    def classify(self, params: dict[str, Any]) -> ActionType:
        operation = str(params.get("operation") or "").lower()
        if not operation and self.default_operation:
            operation = self.default_operation
        return self.operation_action_types.get(operation, self.action_type)


@dataclass
class HealthStatus:
    healthy: bool
    message: str = "ok"
    degraded: bool = False
