"""Thread-safe scheduling of coroutines onto the Chat UI event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from chat_ui.server import ChatUIServer

T = TypeVar("T")
UiCoroutineFactory = Callable[[], Awaitable[T]]


def _log_ui_schedule_error(future: asyncio.Future) -> None:
    if future.cancelled():
        return
    exc = future.exception()
    if exc is not None:
        import logging

        logging.getLogger(__name__).debug("UI schedule failed: %s", exc)


def schedule_ui(chat_ui: ChatUIServer, coro_factory: UiCoroutineFactory) -> None:
    """Run a coroutine on the Chat UI loop from any thread."""

    loop = chat_ui._loop  # noqa: SLF001
    if loop is None or not loop.is_running():
        return
    future = asyncio.run_coroutine_threadsafe(coro_factory(), loop)
    future.add_done_callback(_log_ui_schedule_error)


def make_ui_scheduler(chat_ui: ChatUIServer) -> Callable[[UiCoroutineFactory], None]:
    return lambda factory: schedule_ui(chat_ui, factory)
