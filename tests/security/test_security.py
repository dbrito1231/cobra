"""Tests for the Security component."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from security.anomaly import AnomalyDetector
from security.audit import OutboundAuditLog
from security.auto_lock import AutoLock
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


class TestOutboundAuditLog:
    def test_audit_outbound_writes_json_line(self, tmp_security_config: SecurityConfig) -> None:
        audit = OutboundAuditLog(tmp_security_config.audit_log_path)
        audit.audit_outbound("lm-studio", "topic summary", trigger="P2")
        entries = audit.read_entries()
        assert len(entries) == 1
        assert entries[0]["destination"] == "lm-studio"
        assert entries[0]["sanitized_query"] == "topic summary"


class TestAnomalyDetector:
    def test_blocks_unknown_destination(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        audit = OutboundAuditLog(tmp_security_config.audit_log_path)
        alerts: list = []
        detector = AnomalyDetector(
            tmp_security_config.known_destinations,
            audit,
            tmp_security_config.anomaly_log_path,
            on_alert=alerts.append,
        )
        allowed = detector.check_outbound("evil.example.com", "probe")
        assert allowed is False
        assert len(alerts) == 1
        blocked = audit.read_entries()[-1]
        assert blocked["outcome"] == RequestOutcome.BLOCKED.value

    def test_allows_known_destination(
        self, tmp_security_config: SecurityConfig
    ) -> None:
        audit = OutboundAuditLog(tmp_security_config.audit_log_path)
        detector = AnomalyDetector(
            tmp_security_config.known_destinations,
            audit,
            tmp_security_config.anomaly_log_path,
        )
        assert detector.check_outbound("lm-studio", "health check") is True


class TestAutoLock:
    def test_disabled_when_timeout_zero(self) -> None:
        lock = AutoLock(0)
        assert lock.enabled is False

    def test_unlock_on_activity(self) -> None:
        lock = AutoLock(1)
        lock._locked = True
        lock.record_activity()
        assert lock.locked is False


class TestSecurityService:
    def test_initialize_and_audit(self, tmp_security_config: SecurityConfig) -> None:
        service = SecurityService(tmp_security_config)
        service.initialize()
        service.audit_outbound(
            "lm-studio",
            "model ping",
            approval_status=ApprovalStatus.AUTO,
        )
        entries = service.audit_log.read_entries()
        assert entries
        assert service.health().healthy
        service.shutdown()

    def test_bind_host_respects_network_mode(self) -> None:
        local = SecurityConfig(network_access=NetworkAccessMode.LOCALHOST_ONLY)
        lan = SecurityConfig(network_access=NetworkAccessMode.LOCAL_NETWORK)
        assert local.bind_host == "127.0.0.1"
        assert lan.bind_host == "0.0.0.0"

    def test_from_config_dict_includes_mcp_endpoints(self) -> None:
        config = SecurityConfig.from_config_dict(
            {
                "mcp_servers": [{"endpoint": "http://127.0.0.1:9000"}],
                "model": {"endpoint": "http://127.0.0.1:1234"},
            }
        )
        assert "http://127.0.0.1:9000" in config.known_destinations
        assert "http://127.0.0.1:1234" in config.known_destinations
