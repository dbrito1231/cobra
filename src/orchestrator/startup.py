"""Phased startup per startup-phases.md."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Union

from orchestrator.models import ComponentName, StartupPhase

ComponentStarter = Callable[[], Union[Awaitable[None], None]]
LmStudioProbe = Callable[[], Union[Awaitable[bool], bool]]


@dataclass
class StartupHooks:
    load_configuration: ComponentStarter | None = None
    initialize_security: ComponentStarter | None = None
    initialize_mcp: ComponentStarter | None = None
    wait_lm_studio: LmStudioProbe | None = None
    initialize_brain: ComponentStarter | None = None
    initialize_tools: ComponentStarter | None = None
    initialize_voice: ComponentStarter | None = None
    initialize_chat_ui: ComponentStarter | None = None
    stop_chat_ui: ComponentStarter | None = None
    stop_voice: ComponentStarter | None = None
    stop_tools: ComponentStarter | None = None
    stop_brain: ComponentStarter | None = None
    stop_mcp: ComponentStarter | None = None
    stop_security: ComponentStarter | None = None
    save_configuration: ComponentStarter | None = None


class StartupManager:
    """Runs PHASE1 → PHASE4 with dependency gates."""

    def __init__(
        self,
        hooks: StartupHooks,
        *,
        on_phase: Callable[[StartupPhase], None] | None = None,
        on_component: Callable[[ComponentName, str], None] | None = None,
        lm_retry_interval_seconds: float = 5.0,
    ) -> None:
        self.hooks = hooks
        self._on_phase = on_phase
        self._on_component = on_component
        self.lm_retry_interval_seconds = lm_retry_interval_seconds
        self._lm_cancelled = False

    def cancel_lm_wait(self) -> None:
        self._lm_cancelled = True

    async def run(self) -> bool:
        self._emit_phase(StartupPhase.LAUNCH)

        await self._start_component(
            ComponentName.CONFIGURATION,
            self.hooks.load_configuration,
            StartupPhase.PHASE1,
        )

        self._emit_phase(StartupPhase.PHASE2)
        await asyncio.gather(
            self._start_component(
                ComponentName.SECURITY,
                self.hooks.initialize_security,
                StartupPhase.PHASE2,
            ),
            self._start_component(
                ComponentName.MCP,
                self.hooks.initialize_mcp,
                StartupPhase.PHASE2,
            ),
        )

        if not await self._wait_for_lm_studio():
            return False

        self._emit_phase(StartupPhase.PHASE3)
        await asyncio.gather(
            self._start_component(
                ComponentName.BRAIN,
                self.hooks.initialize_brain,
                StartupPhase.PHASE3,
            ),
            self._start_component(
                ComponentName.TOOLS,
                self.hooks.initialize_tools,
                StartupPhase.PHASE3,
            ),
        )

        self._emit_phase(StartupPhase.PHASE4)
        await asyncio.gather(
            self._start_component(
                ComponentName.VOICE,
                self.hooks.initialize_voice,
                StartupPhase.PHASE4,
            ),
            self._start_component(
                ComponentName.CHAT_UI,
                self.hooks.initialize_chat_ui,
                StartupPhase.PHASE4,
            ),
        )

        self._emit_phase(StartupPhase.READY)
        return True

    async def _wait_for_lm_studio(self) -> bool:
        self._emit_phase(StartupPhase.LM_STUDIO_WAIT)
        probe = self.hooks.wait_lm_studio
        if probe is None:
            return True

        while not self._lm_cancelled:
            result = probe()
            available = await result if asyncio.iscoroutine(result) else result
            if available:
                return True
            await asyncio.sleep(self.lm_retry_interval_seconds)
        return False

    async def _start_component(
        self,
        name: ComponentName,
        starter: ComponentStarter | None,
        phase: StartupPhase,
    ) -> None:
        self._emit_phase(phase)
        if starter is None:
            if self._on_component:
                self._on_component(name, "skipped — no hook")
            return

        result = starter()
        if asyncio.iscoroutine(result):
            await result
        if self._on_component:
            self._on_component(name, "started")

    def _emit_phase(self, phase: StartupPhase) -> None:
        if self._on_phase:
            self._on_phase(phase)
