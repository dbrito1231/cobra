"""Graceful shutdown SD1–SD11."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Union

from orchestrator.models import ComponentName

ShutdownHook = Callable[[], Union[Awaitable[None], None]]


class ShutdownManager:
    """Reverse-order teardown with in-flight response wait."""

    def __init__(
        self,
        *,
        wait_for_response: Callable[[], Union[Awaitable[None], None]] | None = None,
        summarize_session: Callable[[], Union[Awaitable[None], None]] | None = None,
        stop_chat_ui: ShutdownHook | None = None,
        stop_voice: ShutdownHook | None = None,
        stop_tools: ShutdownHook | None = None,
        stop_brain: ShutdownHook | None = None,
        stop_mcp: ShutdownHook | None = None,
        stop_security: ShutdownHook | None = None,
        save_configuration: ShutdownHook | None = None,
    ) -> None:
        self._wait_for_response = wait_for_response
        self._summarize_session = summarize_session
        self._hooks: list[tuple[ComponentName, ShutdownHook | None]] = [
            (ComponentName.CHAT_UI, stop_chat_ui),
            (ComponentName.VOICE, stop_voice),
            (ComponentName.TOOLS, stop_tools),
            (ComponentName.BRAIN, stop_brain),
            (ComponentName.MCP, stop_mcp),
            (ComponentName.SECURITY, stop_security),
            (ComponentName.CONFIGURATION, save_configuration),
        ]

    async def run(self) -> None:
        if self._wait_for_response:
            result = self._wait_for_response()
            if asyncio.iscoroutine(result):
                await result

        if self._summarize_session:
            result = self._summarize_session()
            if asyncio.iscoroutine(result):
                await result

        for _name, hook in self._hooks:
            if hook is None:
                continue
            result = hook()
            if asyncio.iscoroutine(result):
                await result
