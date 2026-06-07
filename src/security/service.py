"""Security service — wires data protection, audit, auto-lock, and anomaly detection."""

from __future__ import annotations

from collections.abc import Callable

from security.anomaly import AnomalyDetector
from security.audit import OutboundAuditLog
from security.auto_lock import AutoLock
from security.config import SecurityConfig
from security.data_protection import protect_cobra_paths
from security.models import AnomalyAlert, ApprovalStatus, HealthStatus, RequestOutcome


class SecurityService:
    """Top-level Security component initialized in Orchestrator Phase 2."""

    def __init__(
        self,
        config: SecurityConfig | None = None,
        *,
        on_lock: Callable[[], None] | None = None,
        on_unlock: Callable[[], None] | None = None,
        on_anomaly: Callable[[AnomalyAlert], None] | None = None,
    ) -> None:
        self.config = config or SecurityConfig.from_env()
        self.audit_log = OutboundAuditLog(self.config.audit_log_path)
        self.auto_lock = AutoLock(
            self.config.auto_lock_timeout_minutes,
            on_lock=on_lock,
            on_unlock=on_unlock,
        )
        self.anomaly = AnomalyDetector(
            self.config.known_destinations,
            self.audit_log,
            self.config.anomaly_log_path,
            on_alert=on_anomaly,
        )
        self._initialized = False

    def initialize(self) -> None:
        """Phase 2 Security init — data protection and audit log ready."""

        protect_cobra_paths(self.config.cobra_dir)
        self.audit_log.ensure_ready()
        self.auto_lock.start()
        self._initialized = True

    def shutdown(self) -> None:
        """Finalize audit log on graceful shutdown (SD9)."""

        self.auto_lock.stop()
        self.audit_log.finalize()
        self._initialized = False

    def audit_outbound(
        self,
        destination: str,
        sanitized_query: str,
        *,
        trigger: str = "pipeline",
        approval_status: ApprovalStatus = ApprovalStatus.AUTO,
        outcome: RequestOutcome = RequestOutcome.SUCCESS,
    ) -> None:
        """Interface contract for all outbound components."""

        if not self.anomaly.check_outbound(
            destination,
            sanitized_query,
            trigger=trigger,
            approval_status=approval_status,
        ):
            self.audit_log.audit_outbound(
                destination,
                sanitized_query,
                trigger=trigger,
                approval_status=approval_status,
                outcome=RequestOutcome.BLOCKED,
            )
            return
        self.audit_log.audit_outbound(
            destination,
            sanitized_query,
            trigger=trigger,
            approval_status=approval_status,
            outcome=outcome,
        )

    def is_input_allowed(self) -> bool:
        return self.auto_lock.is_input_allowed()

    def record_activity(self) -> None:
        self.auto_lock.record_activity()

    def health(self) -> HealthStatus:
        if not self._initialized:
            return HealthStatus(healthy=False, message="not initialized")
        return HealthStatus(healthy=True)

    @property
    def bind_host(self) -> str:
        return self.config.bind_host
