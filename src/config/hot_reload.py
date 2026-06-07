"""Hot reload via polling HR1–HR5."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from config.loader import DEFAULT_CONFIG_PATH, load_config, save_config
from config.models import CobraConfig
from config.validation import validate_config


class HotReloadWatcher:
    """Poll config file mtime and apply valid changes."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        poll_interval_seconds: float = 5.0,
        on_applied: Callable[[CobraConfig], None] | None = None,
        on_reverted: Callable[[str], None] | None = None,
        on_notify: Callable[[str], None] | None = None,
    ) -> None:
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH).expanduser()
        self.poll_interval_seconds = poll_interval_seconds
        self._on_applied = on_applied
        self._on_reverted = on_reverted
        self._on_notify = on_notify
        self._last_mtime: float | None = None
        self._last_valid: CobraConfig | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, baseline: CobraConfig) -> None:
        self._last_valid = baseline
        if self.config_path.exists():
            self._last_mtime = self.config_path.stat().st_mtime
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="config-hot-reload", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_interval_seconds):
            if not self.config_path.exists():
                continue
            mtime = self.config_path.stat().st_mtime
            if self._last_mtime is not None and mtime <= self._last_mtime:
                continue
            self._last_mtime = mtime
            self._handle_change()

    def _handle_change(self) -> None:
        try:
            candidate = load_config(self.config_path)
        except Exception as exc:
            self._revert(f"Config reload failed: {exc}")
            return

        report = validate_config(candidate, config_path=self.config_path)
        if not report.passed:
            message = report.failures()[0].message if report.failures() else "Invalid config"
            self._revert(message)
            return

        self._last_valid = candidate
        if self._on_notify:
            self._on_notify("Configuration updated from disk.")
        if self._on_applied:
            self._on_applied(candidate)

    def _revert(self, message: str) -> None:
        if self._last_valid is not None:
            save_config(self._last_valid, self.config_path)
            if self.config_path.exists():
                self._last_mtime = self.config_path.stat().st_mtime
        if self._on_reverted:
            self._on_reverted(message)
        if self._on_notify:
            self._on_notify(f"Config change rejected: {message}")
