"""LM Studio wait loop LM1–LM4."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Union

from config.models import CobraConfig, ValidationReport


class LmStudioWaiter:
    """Background retry until LM Studio is reachable or user cancels."""

    def __init__(
        self,
        config: CobraConfig,
        *,
        retry_interval_seconds: float = 5.0,
        on_notify: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.retry_interval_seconds = retry_interval_seconds
        self._on_notify = on_notify
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def check_once(self) -> ValidationReport:
        from config.validation import _check_lm_studio

        checks = _check_lm_studio(self.config)
        return ValidationReport(checks=checks)

    def is_ready(self) -> bool:
        return self.check_once().passed

    async def wait(self) -> bool:
        if self._on_notify:
            self._on_notify("LM Studio is not available. Retrying in background...")
        while not self._cancelled:
            if self.is_ready():
                if self._on_notify:
                    self._on_notify("LM Studio is now available.")
                return True
            await asyncio.sleep(self.retry_interval_seconds)
        return False

    def wait_blocking(self, timeout: float | None = None) -> bool:
        start = time.monotonic()
        while not self._cancelled:
            if self.is_ready():
                return True
            if timeout is not None and time.monotonic() - start >= timeout:
                return False
            time.sleep(self.retry_interval_seconds)
        return False
