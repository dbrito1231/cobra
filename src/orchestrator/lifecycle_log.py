"""Lifecycle logging L1–L5 at ~/.cobra/logs/orchestrator.log."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from orchestrator.models import ComponentName, LifecycleEventType, LifecycleLogEntry

DEFAULT_LOG_PATH = Path.home() / ".cobra" / "logs" / "orchestrator.log"


class LifecycleLogger:
    """Append-only JSON-lines orchestrator lifecycle log."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = Path(log_path or DEFAULT_LOG_PATH).expanduser()
        self._lock = threading.Lock()

    def ensure_ready(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()

    def log(
        self,
        component: ComponentName,
        event_type: LifecycleEventType,
        *,
        trigger: str,
        outcome: str,
        message: str = "",
    ) -> LifecycleLogEntry:
        entry = LifecycleLogEntry(
            component=component,
            event_type=event_type,
            trigger=trigger,
            outcome=outcome,
            message=message,
        )
        line = json.dumps(entry.to_dict(), ensure_ascii=True) + "\n"
        with self._lock:
            self.ensure_ready()
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        return entry

    def read_entries(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        entries: list[dict] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
        return entries
