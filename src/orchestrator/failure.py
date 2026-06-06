"""Failure response F1–F8 — user-driven, no silent retry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Union

from orchestrator.models import ComponentName, FailureAction, HealthState

FailurePromptHandler = Callable[
    [ComponentName, HealthState, str],
    Union[Awaitable[FailureAction], FailureAction],
]
ComponentRestarter = Callable[[ComponentName], Union[Awaitable[bool], bool]]
FullRestarter = Callable[[], Union[Awaitable[None], None]]


class FailureResponder:
    """Handle degraded/failed components per user choice."""

    def __init__(
        self,
        *,
        prompt: FailurePromptHandler | None = None,
        restart_component: ComponentRestarter | None = None,
        restart_all: FullRestarter | None = None,
        mark_unavailable: Callable[[ComponentName], None] | None = None,
        mark_healthy: Callable[[ComponentName], None] | None = None,
    ) -> None:
        self._prompt = prompt
        self._restart_component = restart_component
        self._restart_all = restart_all
        self._mark_unavailable = mark_unavailable
        self._mark_healthy = mark_healthy

    async def handle(
        self,
        name: ComponentName,
        state: HealthState,
        message: str,
    ) -> FailureAction:
        if self._prompt is None:
            return FailureAction.IGNORE

        action_result = self._prompt(name, state, message)
        action = await action_result if hasattr(action_result, "__await__") else action_result

        if action == FailureAction.RESTART_COMPONENT:
            success = await self._do_restart(name)
            if success:
                if self._mark_healthy:
                    self._mark_healthy(name)
            else:
                return await self.handle(name, HealthState.FAILED, "restart failed")
        elif action == FailureAction.IGNORE:
            if self._mark_unavailable:
                self._mark_unavailable(name)
        elif action == FailureAction.RESTART_ALL and self._restart_all:
            result = self._restart_all()
            if hasattr(result, "__await__"):
                await result

        return action

    async def _do_restart(self, name: ComponentName) -> bool:
        if self._restart_component is None:
            return False
        result = self._restart_component(name)
        if hasattr(result, "__await__"):
            return bool(await result)
        return bool(result)
