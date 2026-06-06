"""Orchestrator data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ComponentName(str, Enum):
    CONFIGURATION = "configuration"
    SECURITY = "security"
    MCP = "mcp"
    BRAIN = "brain"
    VOICE = "voice"
    CHAT_UI = "chat_ui"
    TOOLS = "tools"
    ORCHESTRATOR = "orchestrator"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RESTARTING = "restarting"
    UNAVAILABLE = "unavailable"


class StartupPhase(str, Enum):
    LAUNCH = "launch"
    PHASE1 = "phase1"
    PHASE2 = "phase2"
    LM_STUDIO_WAIT = "lm_studio_wait"
    PHASE3 = "phase3"
    PHASE4 = "phase4"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"


class LifecycleEventType(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERED = "recovered"


class FailureAction(str, Enum):
    RESTART_COMPONENT = "restart_component"
    IGNORE = "ignore"
    RESTART_ALL = "restart_all"


@dataclass
class ComponentRecord:
    name: ComponentName
    dependencies: tuple[ComponentName, ...]
    state: HealthState = HealthState.UNAVAILABLE
    message: str = "not started"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "dependencies": [item.value for item in self.dependencies],
            "state": self.state.value,
            "message": self.message,
        }


@dataclass
class LifecycleLogEntry:
    component: ComponentName
    event_type: LifecycleEventType
    trigger: str
    outcome: str
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component.value,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "trigger": self.trigger,
            "outcome": self.outcome,
            "message": self.message,
        }


@dataclass
class BusEvent:
    """Inter-component event routed through the orchestrator."""

    topic: str
    source: ComponentName
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "source": self.source.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }
