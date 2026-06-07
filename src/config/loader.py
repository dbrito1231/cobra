"""Load and save ~/.cobra/config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.models import CobraConfig, ProfileConfig

DEFAULT_CONFIG_PATH = Path.home() / ".cobra" / "config.yaml"


def default_config() -> CobraConfig:
    """Return a valid default configuration."""

    return CobraConfig(
        profiles={
            "default": ProfileConfig(name="Default"),
        }
    )


def load_config(path: Path | None = None) -> CobraConfig:
    """Load config from disk; raise FileNotFoundError if missing."""

    config_path = Path(path or DEFAULT_CONFIG_PATH).expanduser()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return CobraConfig.from_dict(raw)


def save_config(config: CobraConfig, path: Path | None = None) -> Path:
    """Persist config as human-readable YAML."""

    config_path = Path(path or DEFAULT_CONFIG_PATH).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="python")
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return config_path


def ensure_config(path: Path | None = None) -> CobraConfig:
    """Create default config file if missing and return loaded config."""

    config_path = Path(path or DEFAULT_CONFIG_PATH).expanduser()
    if not config_path.exists():
        save_config(default_config(), config_path)
    return load_config(config_path)


def config_to_legacy_dict(config: CobraConfig) -> dict[str, Any]:
    """Flatten active profile for components that consume dict payloads."""

    profile = config.active()
    storage = profile.storage.expand()
    return {
        "version": config.version,
        "active_profile": config.active_profile,
        "profiles": {
            key: value.model_dump(mode="python") for key, value in config.profiles.items()
        },
        "ui": config.ui,
        "model": profile.model.model_dump(),
        "api_keys": profile.api_keys.model_dump(),
        "storage": {key: str(path) for key, path in storage.items()},
        "mcp_servers": [server.model_dump() for server in profile.mcp_servers],
        "personality_mode": profile.personality_mode,
        "tool_sandbox": profile.tool_sandbox,
        "voice": profile.voice,
        "security": profile.security,
    }
