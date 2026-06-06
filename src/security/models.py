"""Security data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    AUTO = "auto"


class RequestOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class NetworkAccessMode(str, Enum):
    LOCALHOST_ONLY = "localhost_only"
    LOCAL_NETWORK = "local_network"


@dataclass
class AuditEntry:
    """Single outbound audit log row (AU1–AU6)."""

    destination: str
    sanitized_query: str
    trigger: str
    approval_status: ApprovalStatus
    outcome: RequestOutcome
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "destination": self.destination,
            "sanitized_query": self.sanitized_query,
            "trigger": self.trigger,
            "approval_status": self.approval_status.value,
            "outcome": self.outcome.value,
        }


@dataclass
class AnomalyAlert:
    """Unexpected outbound connection alert (OB5–OB7)."""

    destination: str
    sanitized_detail: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "destination": self.destination,
            "detail": self.sanitized_detail,
        }


@dataclass
class HealthStatus:
    """Component health snapshot for orchestrator pings."""

    healthy: bool
    message: str = "ok"
    degraded: bool = False
