"""Main orchestrator — wires startup, health, event bus, and shutdown."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Union

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
from orchestrator.registry import ComponentRegistry
from orchestrator.shutdown import ShutdownManager
from orchestrator.startup import StartupHooks, StartupManager

HealthProvider = Callable[[], tuple[bool, str, bool]]


class Orchestrator:
    """Top-level C.O.B.R.A. manager — first to start, last to stop."""

    def __init__(
        self,
        *,
        log_path: Path | None = None,
        health_config: HealthMonitorConfig | None = None,
        hooks: StartupHooks | None = None,
        health_providers: dict[ComponentName, HealthProvider] | None = None,
        failure_prompt: Callable[
            [ComponentName, HealthState, str],
            Union[Awaitable[FailureAction], FailureAction],
        ]
        | None = None,
    ) -> None:
        self.registry = ComponentRegistry()
        self.logger = LifecycleLogger(log_path)
        self.bus = EventBus()
        self.health = HealthMonitor(health_config, on_unhealthy=self._schedule_unhealthy)
        self.phase = StartupPhase.LAUNCH
        self.ready = False
        self._hooks = hooks or StartupHooks()
        self._health_providers = health_providers or {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._response_in_progress = threading.Event()
        self._failure_responder = FailureResponder(
            prompt=failure_prompt,
            restart_component=self.restart_component,
            restart_all=self.restart_all,
            mark_unavailable=self._mark_unavailable,
            mark_healthy=self._mark_healthy,
        )
        self._startup = StartupManager(
            self._hooks,
            on_phase=self._set_phase,
            on_component=self._on_component_started,
        )
        self._shutdown = ShutdownManager(
            wait_for_response=self._wait_for_response,
            summarize_session=self._summarize_session,
            stop_chat_ui=self._hooks.stop_chat_ui,
            stop_voice=self._hooks.stop_voice,
            stop_tools=self._hooks.stop_tools,
            stop_brain=self._hooks.stop_brain,
            stop_mcp=self._hooks.stop_mcp,
            stop_security=self._hooks.stop_security,
            save_configuration=self._hooks.save_configuration,
        )

        for name, provider in self._health_providers.items():
            self.health.register(name, provider)

    async def start(self) -> bool:
        self.logger.log(
            ComponentName.ORCHESTRATOR,
            LifecycleEventType.START,
            trigger="startup",
            outcome="success",
        )
        success = await self._startup.run()
        if not success:
            self.logger.log(
                ComponentName.ORCHESTRATOR,
                LifecycleEventType.FAILED,
                trigger="startup",
                outcome="failure",
                message="LM Studio wait cancelled",
            )
            return False

        for name in self._health_providers:
            self.registry.mark_state(name, HealthState.HEALTHY)
        self.health.start()
        self.ready = True
        self.bus.route("system.ready", ComponentName.ORCHESTRATOR, {"phase": self.phase.value})
        return True

    async def shutdown(self) -> None:
        self._set_phase(StartupPhase.SHUTTING_DOWN)
        self.health.stop()
        await self._shutdown.run()
        self.ready = False
        self.logger.log(
            ComponentName.ORCHESTRATOR,
            LifecycleEventType.STOP,
            trigger="shutdown",
            outcome="success",
        )

    def publish(
        self,
        topic: str,
        source: ComponentName,
        payload: dict[str, Any] | None = None,
    ) -> BusEvent:
        return self.bus.route(topic, source, payload)

    def subscribe(self, topic: str, handler: Callable[[BusEvent], None]) -> None:
        self.bus.subscribe(topic, handler)

    def register_health(self, name: ComponentName, provider: HealthProvider) -> None:
        self._health_providers[name] = provider
        self.health.register(name, provider)

    def set_response_in_progress(self, active: bool) -> None:
        if active:
            self._response_in_progress.set()
        else:
            self._response_in_progress.clear()

    def cancel_lm_wait(self) -> None:
        self._startup.cancel_lm_wait()

    async def restart_component(self, name: ComponentName) -> bool:
        self.registry.mark_state(name, HealthState.RESTARTING)
        self.logger.log(
            name,
            LifecycleEventType.RESTART,
            trigger="user",
            outcome="pending",
        )
        starter = self._starter_for(name)
        if starter is None:
            return False
        result = starter()
        if asyncio.iscoroutine(result):
            await result
        self.registry.mark_state(name, HealthState.HEALTHY)
        self.logger.log(
            name,
            LifecycleEventType.RECOVERED,
            trigger="restart",
            outcome="success",
        )
        return True

    async def restart_all(self) -> None:
        await self.shutdown()
        await self.start()

    def _starter_for(self, name: ComponentName):
        mapping = {
            ComponentName.CONFIGURATION: self._hooks.load_configuration,
            ComponentName.SECURITY: self._hooks.initialize_security,
            ComponentName.MCP: self._hooks.initialize_mcp,
            ComponentName.BRAIN: self._hooks.initialize_brain,
            ComponentName.TOOLS: self._hooks.initialize_tools,
            ComponentName.VOICE: self._hooks.initialize_voice,
            ComponentName.CHAT_UI: self._hooks.initialize_chat_ui,
        }
        return mapping.get(name)

    def _set_phase(self, phase: StartupPhase) -> None:
        self.phase = phase
        self.publish("system.phase", ComponentName.ORCHESTRATOR, {"phase": phase.value})

    def _on_component_started(self, name: ComponentName, message: str) -> None:
        self.registry.mark_state(name, HealthState.HEALTHY, message=message)
        self.logger.log(
            name,
            LifecycleEventType.START,
            trigger="startup",
            outcome="success",
            message=message,
        )

    def _mark_unavailable(self, name: ComponentName) -> None:
        self.registry.mark_state(name, HealthState.UNAVAILABLE)

    def _mark_healthy(self, name: ComponentName) -> None:
        self.registry.mark_state(name, HealthState.HEALTHY)

    def _schedule_unhealthy(
        self,
        name: ComponentName,
        state: HealthState,
        message: str,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._on_unhealthy(name, state, message))
            return
        loop.create_task(self._on_unhealthy(name, state, message))

    async def _on_unhealthy(
        self,
        name: ComponentName,
        state: HealthState,
        message: str,
    ) -> None:
        self.registry.mark_state(name, state, message=message)
        self.logger.log(
            name,
            LifecycleEventType.DEGRADED if state == HealthState.DEGRADED else LifecycleEventType.FAILED,
            trigger="health_check",
            outcome=state.value,
            message=message,
        )
        self.publish(
            "system.health",
            ComponentName.ORCHESTRATOR,
            {"component": name.value, "state": state.value, "message": message},
        )
        await self._failure_responder.handle(name, state, message)

    async def _wait_for_response(self) -> None:
        while self._response_in_progress.is_set():
            await asyncio.sleep(0.1)

    async def _summarize_session(self) -> None:
        self.publish(
            "brain.summarize_session",
            ComponentName.ORCHESTRATOR,
            {},
        )
