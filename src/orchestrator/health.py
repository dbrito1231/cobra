"""Continuous health monitoring H1–H5."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from orchestrator.models import ComponentName, HealthState

HealthProbe = Callable[[], tuple[bool, str, bool]]


@dataclass(frozen=True)
class HealthMonitorConfig:
    ping_interval_seconds: float = 10.0
    timeout_seconds: float = 3.0


class HealthMonitor:
    """Ping registered components and surface degraded/failed states."""

    def __init__(
        self,
        config: HealthMonitorConfig | None = None,
        *,
        on_unhealthy: Callable[[ComponentName, HealthState, str], None] | None = None,
    ) -> None:
        self.config = config or HealthMonitorConfig()
        self._probes: dict[ComponentName, HealthProbe] = {}
        self._states: dict[ComponentName, HealthState] = {}
        self._messages: dict[ComponentName, str] = {}
        self._on_unhealthy = on_unhealthy
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def register(self, name: ComponentName, probe: HealthProbe) -> None:
        self._probes[name] = probe
        self._states[name] = HealthState.UNAVAILABLE

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="health-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def check_once(self) -> dict[ComponentName, HealthState]:
        for name, probe in self._probes.items():
            try:
                healthy, message, degraded = probe()
            except Exception as exc:  # noqa: BLE001 — health probe boundary
                healthy, message, degraded = False, str(exc), False

            if not healthy:
                state = HealthState.FAILED
            elif degraded:
                state = HealthState.DEGRADED
            else:
                state = HealthState.HEALTHY

            previous = self._states.get(name)
            self._states[name] = state
            self._messages[name] = message
            if state in {HealthState.FAILED, HealthState.DEGRADED} and state != previous:
                if self._on_unhealthy:
                    self._on_unhealthy(name, state, message)
        return dict(self._states)

    def message_for(self, name: ComponentName) -> str:
        return self._messages.get(name, "")

    def _loop(self) -> None:
        while not self._stop.wait(self.config.ping_interval_seconds):
            self.check_once()
