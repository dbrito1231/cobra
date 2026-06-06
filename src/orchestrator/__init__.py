"""C.O.B.R.A. Orchestrator — startup, health, event bus, shutdown."""

from orchestrator.bootstrap import build_default_orchestrator
from orchestrator.event_bus import EventBus
from orchestrator.failure import FailureResponder
from orchestrator.health import HealthMonitor, HealthMonitorConfig
from orchestrator.lifecycle_log import LifecycleLogger
from orchestrator.models import (
    BusEvent,
    ComponentName,
    FailureAction,
    HealthState,
    LifecycleEventType,
    StartupPhase,
)
from orchestrator.orchestrator import Orchestrator
from orchestrator.registry import ComponentRegistry
from orchestrator.shutdown import ShutdownManager
from orchestrator.startup import StartupHooks, StartupManager

__all__ = [
    "BusEvent",
    "ComponentName",
    "ComponentRegistry",
    "EventBus",
    "FailureAction",
    "FailureResponder",
    "HealthMonitor",
    "HealthMonitorConfig",
    "HealthState",
    "LifecycleEventType",
    "LifecycleLogger",
    "Orchestrator",
    "ShutdownManager",
    "StartupHooks",
    "StartupManager",
    "StartupPhase",
    "build_default_orchestrator",
]
