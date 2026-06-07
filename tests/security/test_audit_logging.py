"""Audit logging consistency tests for SecurityService."""

from __future__ import annotations

from pathlib import Path

import pytest

from security.config import SecurityConfig
from security.models import ApprovalStatus, NetworkAccessMode, RequestOutcome
from security.service import SecurityService


@pytest.fixture
def tmp_security_config(tmp_path: Path) -> SecurityConfig:
    logs = tmp_path / "logs"
    return SecurityConfig(
        auto_lock_timeout_minutes=0,
        network_access=NetworkAccessMode.LOCALHOST_ONLY,
        cobra_dir=tmp_path,
        audit_log_path=logs / "outbound-audit.log",
        anomaly_log_path=logs / "anomaly.log",
        known_destinations=("lm-studio", "http://127.0.0.1:1234"),
    )


class TestAuditLoggingConsistency:
    def test_success_logged_once_with_fields(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        service = SecurityService(tmp_security_config)
        service.initialize()
        service.audit_outbound(
            "lm-studio",
            "model ping",
            trigger="P2",
            approval_status=ApprovalStatus.AUTO,
            outcome=RequestOutcome.SUCCESS,
        )
        entries = service.audit_log.read_entries()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["destination"] == "lm-studio"
        assert entry["sanitized_query"] == "model ping"
        assert entry["trigger"] == "P2"
        assert entry["approval_status"] == ApprovalStatus.AUTO.value
        assert entry["outcome"] == RequestOutcome.SUCCESS.value
        service.shutdown()

    def test_failure_logged_with_outcome(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        service = SecurityService(tmp_security_config)
        service.initialize()
        service.audit_outbound(
            "http://127.0.0.1:1234",
            "timeout probe",
            trigger="P3",
            approval_status=ApprovalStatus.APPROVED,
            outcome=RequestOutcome.TIMEOUT,
        )
        entries = service.audit_log.read_entries()
        assert len(entries) == 1
        assert entries[0]["approval_status"] == ApprovalStatus.APPROVED.value
        assert entries[0]["outcome"] == RequestOutcome.TIMEOUT.value
        service.shutdown()

    def test_blocked_unknown_destination_logged_once(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        service = SecurityService(tmp_security_config)
        service.initialize()
        service.audit_outbound(
            "evil.example.com",
            "probe",
            trigger="pipeline",
            approval_status=ApprovalStatus.AUTO,
            outcome=RequestOutcome.SUCCESS,
        )
        entries = service.audit_log.read_entries()
        assert len(entries) == 1
        assert entries[0]["destination"] == "evil.example.com"
        assert entries[0]["outcome"] == RequestOutcome.BLOCKED.value
        service.shutdown()

    def test_no_duplicate_on_success(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        service = SecurityService(tmp_security_config)
        service.initialize()
        for _ in range(3):
            service.audit_outbound(
                "lm-studio",
                "repeat ping",
                approval_status=ApprovalStatus.DENIED,
                outcome=RequestOutcome.SUCCESS,
            )
        entries = service.audit_log.read_entries()
        assert len(entries) == 3
        assert all(entry["outcome"] == RequestOutcome.SUCCESS.value for entry in entries)
        assert all(
            entry["approval_status"] == ApprovalStatus.DENIED.value for entry in entries
        )
        service.shutdown()

    def test_denied_mcp_style_outcome(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        service = SecurityService(tmp_security_config)
        service.initialize()
        service.audit_outbound(
            "http://127.0.0.1:1234",
            "web lookup",
            trigger="pipeline",
            approval_status=ApprovalStatus.DENIED,
            outcome=RequestOutcome.BLOCKED,
        )
        entries = service.audit_log.read_entries()
        assert len(entries) == 1
        assert entries[0]["approval_status"] == ApprovalStatus.DENIED.value
        assert entries[0]["outcome"] == RequestOutcome.BLOCKED.value
        service.shutdown()
