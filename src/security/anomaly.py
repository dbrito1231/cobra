"""Application-level outbound anomaly detection per anomaly-detection.md."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from security.models import AnomalyAlert, ApprovalStatus
from security.audit import OutboundAuditLog
from security.privacy import sanitize_query


class AnomalyDetector:
    """Allow known destinations; block and alert on unexpected outbound calls."""

    def __init__(
        self,
        known_destinations: tuple[str, ...],
        audit_log: OutboundAuditLog,
        anomaly_log_path: Path,
        *,
        on_alert: Callable[[AnomalyAlert], None] | None = None,
    ) -> None:
        self.known_destinations = tuple(
            self._normalize_destination(item) for item in known_destinations
        )
        self.audit_log = audit_log
        self.anomaly_log_path = Path(anomaly_log_path).expanduser()
        self._on_alert = on_alert
        self._lock = threading.Lock()

    def check_outbound(
        self,
        destination: str,
        sanitized_query: str,
        *,
        trigger: str = "pipeline",
        approval_status: ApprovalStatus = ApprovalStatus.AUTO,
    ) -> bool:
        """Return True if request may proceed; False if blocked (OB3–OB7)."""

        normalized = self._normalize_destination(destination)
        if self._is_known(normalized):
            return True

        alert = AnomalyAlert(
            destination=destination,
            sanitized_detail=sanitize_query(sanitized_query),
        )
        self._record_anomaly(alert)
        if self._on_alert:
            self._on_alert(alert)
        return False

    def update_known_destinations(self, destinations: tuple[str, ...]) -> None:
        self.known_destinations = tuple(
            self._normalize_destination(item) for item in destinations
        )

    def _is_known(self, normalized: str) -> bool:
        for known in self.known_destinations:
            if normalized == known or normalized.startswith(known):
                return True
        return False

    def _record_anomaly(self, alert: AnomalyAlert) -> None:
        line = json.dumps(alert.to_dict(), ensure_ascii=True) + "\n"
        with self._lock:
            self.anomaly_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.anomaly_log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    @staticmethod
    def _normalize_destination(destination: str) -> str:
        value = destination.strip().lower()
        if "://" in value:
            parsed = urlparse(value)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        return value.rstrip("/")
