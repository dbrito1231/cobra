"""Blocking approval waits for MCP and brain outbound prompts."""

from __future__ import annotations

import asyncio


class ApprovalWaitRegistry:
    """Resolve chat UI approval cards back to awaiting coroutines."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[bool]] = {}

    def register(self, event_id: str) -> asyncio.Future[bool]:
        """Create a future that completes when the user approves or denies."""

        existing = self._pending.pop(event_id, None)
        if existing is not None and not existing.done():
            existing.set_result(False)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[event_id] = future
        return future

    def resolve(self, event_id: str, approved: bool) -> bool:
        """Complete a pending wait. Returns True when a waiter was resolved."""

        future = self._pending.pop(event_id, None)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

    def cancel_all(self, *, approved: bool = False) -> None:
        """Fail or approve all outstanding waits during shutdown."""

        for future in self._pending.values():
            if not future.done():
                future.set_result(approved)
        self._pending.clear()
