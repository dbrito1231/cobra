"""Blocking failure prompt waits for orchestrator health responses."""

from __future__ import annotations

import asyncio


class FailureWaitRegistry:
    """Resolve failure prompt cards back to awaiting coroutines."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[str]] = {}

    def register(self, event_id: str) -> asyncio.Future[str]:
        existing = self._pending.pop(event_id, None)
        if existing is not None and not existing.done():
            existing.set_result("ignore")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending[event_id] = future
        return future

    def resolve(self, event_id: str, action: str) -> bool:
        future = self._pending.pop(event_id, None)
        if future is None or future.done():
            return False
        future.set_result(action)
        return True
