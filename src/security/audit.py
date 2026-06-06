"""Outbound audit logging per outbound-audit-log.md AU1–AU7."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from security.models import ApprovalStatus, AuditEntry, RequestOutcome
from security.privacy import sanitize_query


class OutboundAuditLog:
    """Append-only JSON-lines audit log at ~/.cobra/logs/outbound-audit.log."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = Path(log_path).expanduser()
        self._lock = threading.Lock()

    def ensure_ready(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()

    def audit_outbound(
        self,
        destination: str,
        sanitized_query: str,
        *,
        trigger: str = "pipeline",
        approval_status: ApprovalStatus = ApprovalStatus.AUTO,
        outcome: RequestOutcome = RequestOutcome.SUCCESS,
    ) -> AuditEntry:
        """Primary interface contract: audit_outbound(destination, topic, sanitized_payload)."""

        entry = AuditEntry(
            destination=destination,
            sanitized_query=sanitize_query(sanitized_query),
            trigger=trigger,
            approval_status=approval_status,
            outcome=outcome,
        )
        self._append(entry)
        return entry

    def _append(self, entry: AuditEntry) -> None:
        line = json.dumps(entry.to_dict(), ensure_ascii=True) + "\n"
        with self._lock:
            self.ensure_ready()
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def read_entries(self) -> list[dict]:
        """Read all audit entries (for tests and future Chat UI panel)."""

        if not self.log_path.exists():
            return []
        entries: list[dict] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
        return entries

    def finalize(self) -> None:
        """Flush on shutdown (SD9). Nothing to flush for append-only file."""

        self.ensure_ready()
