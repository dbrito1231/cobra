"""Tests for blocking approval waits."""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.approval_wait import ApprovalWaitRegistry


class TestApprovalWaitRegistry:
    @pytest.mark.asyncio
    async def test_resolve_unblocks_waiter(self) -> None:
        registry = ApprovalWaitRegistry()
        future = registry.register("event-1")

        async def resolve_later() -> None:
            await asyncio.sleep(0.01)
            registry.resolve("event-1", True)

        task = asyncio.create_task(resolve_later())
        assert await future is True
        await task

    @pytest.mark.asyncio
    async def test_deny_returns_false(self) -> None:
        registry = ApprovalWaitRegistry()
        future = registry.register("event-2")

        async def deny_later() -> None:
            await asyncio.sleep(0.01)
            registry.resolve("event-2", False)

        task = asyncio.create_task(deny_later())
        assert await future is False
        await task

    def test_resolve_unknown_event_returns_false(self) -> None:
        registry = ApprovalWaitRegistry()
        assert registry.resolve("missing", True) is False

    @pytest.mark.asyncio
    async def test_reregister_cancels_previous_wait(self) -> None:
        registry = ApprovalWaitRegistry()
        first = registry.register("dup")
        registry.register("dup")
        assert await first is False

    @pytest.mark.asyncio
    async def test_cancel_all(self) -> None:
        registry = ApprovalWaitRegistry()
        future = registry.register("shutdown")
        registry.cancel_all(approved=False)
        assert await future is False
