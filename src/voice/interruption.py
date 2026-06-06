"""Interruption queue IR1–IR4."""

from __future__ import annotations

from collections import deque


class InterruptionQueue:
    """Queue user speech during response playback; process after completion."""

    def __init__(self) -> None:
        self._queue: deque[str] = deque()
        self._responding = False

    @property
    def responding(self) -> bool:
        return self._responding

    def begin_response(self) -> None:
        self._responding = True

    def end_response(self) -> str | None:
        self._responding = False
        if self._queue:
            return self._queue.popleft()
        return None

    def enqueue(self, text: str) -> None:
        if not text.strip():
            return
        if self._responding:
            self._queue.append(text.strip())
        else:
            self._queue.appendleft(text.strip())

    def pop_next(self) -> str | None:
        if self._queue:
            return self._queue.popleft()
        return None
