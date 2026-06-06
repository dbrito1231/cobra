"""Configurable inactivity auto-lock per auto-lock.md AL1–AL6."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class AutoLock:
    """Monitors inactivity and toggles lock state for Voice and Chat UI."""

    def __init__(
        self,
        timeout_minutes: int,
        *,
        on_lock: Callable[[], None] | None = None,
        on_unlock: Callable[[], None] | None = None,
    ) -> None:
        self.timeout_minutes = timeout_minutes
        self._on_lock = on_lock
        self._on_unlock = on_unlock
        self._locked = False
        self._last_activity = time.monotonic()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return self.timeout_minutes > 0

    @property
    def locked(self) -> bool:
        return self._locked

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._monitor, name="auto-lock", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def record_activity(self) -> None:
        """Reset inactivity timer; unlock if user interacts while locked (AL5)."""

        self._last_activity = time.monotonic()
        if self._locked:
            self.unlock()

    def unlock(self) -> None:
        if not self._locked:
            return
        self._locked = False
        if self._on_unlock:
            self._on_unlock()

    def _lock(self) -> None:
        if self._locked:
            return
        self._locked = True
        if self._on_lock:
            self._on_lock()

    def _monitor(self) -> None:
        timeout_seconds = self.timeout_minutes * 60
        while not self._stop.wait(1.0):
            if self._locked:
                continue
            elapsed = time.monotonic() - self._last_activity
            if elapsed >= timeout_seconds:
                self._lock()

    def is_input_allowed(self) -> bool:
        """Voice and text input disabled when locked (AL4)."""

        return not self._locked
