"""Thread-safe scheduling of coroutines onto the Chat UI event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from chat_ui.server import ChatUIServer

T = TypeVar("T")
UiCoroutineFactory = Callable[[], Awaitable[T]]


def schedule_ui(chat_ui: ChatUIServer, coro_factory: UiCoroutineFactory) -> None:
    """Run a coroutine on the Chat UI loop from any thread."""

    loop = chat_ui._loop  # noqa: SLF001
    if loop is None or not loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(coro_factory(), loop)
