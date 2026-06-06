"""Security configuration with defaults until the config agent is available."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from security.models import NetworkAccessMode


DEFAULT_COBRA_DIR = Path.home() / ".cobra"
DEFAULT_LOGS_DIR = DEFAULT_COBRA_DIR / "logs"
DEFAULT_AUDIT_LOG = DEFAULT_LOGS_DIR / "outbound-audit.log"
DEFAULT_ANOMALY_LOG = DEFAULT_LOGS_DIR / "anomaly.log"


@dataclass(frozen=True)
class SecurityConfig:
    """Resolved security settings."""

    auto_lock_timeout_minutes: int = 0
    network_access: NetworkAccessMode = NetworkAccessMode.LOCALHOST_ONLY
    cobra_dir: Path = DEFAULT_COBRA_DIR
    audit_log_path: Path = DEFAULT_AUDIT_LOG
    anomaly_log_path: Path = DEFAULT_ANOMALY_LOG
    known_destinations: tuple[str, ...] = (
        "claude-api",
        "copilot-api",
        "lm-studio",
    )

    @classmethod
    def from_env(cls) -> SecurityConfig:
        mode = os.environ.get("COBRA_NETWORK_ACCESS", "localhost_only")
        return cls(
            auto_lock_timeout_minutes=int(
                os.environ.get("COBRA_AUTO_LOCK_MINUTES", "0")
            ),
            network_access=NetworkAccessMode(mode),
            cobra_dir=Path(os.environ.get("COBRA_DIR", DEFAULT_COBRA_DIR)),
        )

    @classmethod
    def from_config_dict(cls, data: dict) -> SecurityConfig:
        """Build from a future config reader API payload."""
        security = data.get("security") or {}
        storage = data.get("storage") or {}
        cobra_dir = Path(os.path.expanduser(storage.get("root", DEFAULT_COBRA_DIR)))
        logs_dir = cobra_dir / "logs"

        known: list[str] = [
            "claude-api",
            "copilot-api",
            "lm-studio",
        ]
        mcp_servers = data.get("mcp_servers") or []
        for server in mcp_servers:
            endpoint = server.get("endpoint") or server.get("url")
            if endpoint:
                known.append(str(endpoint))

        model = data.get("model") or {}
        if model.get("endpoint"):
            known.append(str(model["endpoint"]))

        mode_raw = security.get("network_access", "localhost_only")
        return cls(
            auto_lock_timeout_minutes=int(
                security.get("auto_lock_timeout_minutes", 0)
            ),
            network_access=NetworkAccessMode(mode_raw),
            cobra_dir=cobra_dir,
            audit_log_path=logs_dir / "outbound-audit.log",
            anomaly_log_path=logs_dir / "anomaly.log",
            known_destinations=tuple(dict.fromkeys(known)),
        )

    @property
    def bind_host(self) -> str:
        """Resolve server bind address per network-access.md NW1–NW3."""
        if self.network_access == NetworkAccessMode.LOCAL_NETWORK:
            return "0.0.0.0"
        return "127.0.0.1"
