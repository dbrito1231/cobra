"""Immutable raw conversation logs — Layer M0."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from brain.models import RawLogEntry


class RawLogStore:
    """Append-only immutable conversation log."""

    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.raw_dir = memory_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = str(uuid4())

    @property
    def session_id(self) -> str:
        return self._session_id

    def new_session(self) -> str:
        self._session_id = str(uuid4())
        return self._session_id

    def append(self, entry: RawLogEntry) -> None:
        path = self.raw_dir / f"{entry.session_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict()) + "\n")

    def read_session(self, session_id: str | None = None) -> list[RawLogEntry]:
        sid = session_id or self._session_id
        path = self.raw_dir / f"{sid}.jsonl"
        if not path.exists():
            return []
        entries: list[RawLogEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            entries.append(
                RawLogEntry(
                    session_id=data["session_id"],
                    sender=data["sender"],
                    content=data["content"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    mood=data.get("mood"),
                )
            )
        return entries

    def list_sessions(self) -> list[str]:
        return sorted(path.stem for path in self.raw_dir.glob("*.jsonl"))
