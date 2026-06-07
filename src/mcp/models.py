"""MCP layer data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from config.models import McpServerEntry, SUPPORTED_MCP_PROTOCOL


class ServerAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    VALIDATING = "validating"


class CallOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"


@dataclass
class RegistryEntry:
    server: McpServerEntry
    status: ServerAvailability = ServerAvailability.VALIDATING
    declared_capabilities: list[str] = field(default_factory=list)
    protocol_version: str = SUPPORTED_MCP_PROTOCOL
    message: str = ""

    def to_status_dict(self) -> dict[str, str]:
        return {
            "name": self.server.name,
            "status": self.status.value,
            "endpoint": self.server.endpoint,
        }


@dataclass
class McpApprovalRequest:
    event_id: str
    server_name: str
    capability: str
    sanitized_query: str
    reason: str

    @classmethod
    def create(
        cls,
        server_name: str,
        capability: str,
        sanitized_query: str,
        *,
        reason: str = "MCP call requires explicit approval before execution.",
    ) -> McpApprovalRequest:
        return cls(
            event_id=str(uuid4()),
            server_name=server_name,
            capability=capability,
            sanitized_query=sanitized_query,
            reason=reason,
        )


@dataclass
class McpCallResult:
    success: bool
    capability: str
    server_name: str
    output: Any = None
    outcome: CallOutcome = CallOutcome.SUCCESS
    error: str | None = None
    approval_granted: bool = True


@dataclass
class McpLogEntry:
    server_name: str
    endpoint: str
    capability: str
    sanitized_query: str
    response_summary: str
    outcome: CallOutcome
    approval: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HealthStatus:
    healthy: bool = True
    message: str = "ok"
    degraded: bool = False
