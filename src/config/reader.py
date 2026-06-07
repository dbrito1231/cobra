"""Read-only typed accessors for each config block."""

from __future__ import annotations

from pathlib import Path

from config.models import CobraConfig, McpServerEntry, ModelConfig, ProfileConfig, StorageConfig


class ConfigReader:
    """Interface contract: read-only accessors; raises on missing required keys."""

    def __init__(self, config: CobraConfig) -> None:
        self._config = config

    @property
    def config(self) -> CobraConfig:
        return self._config

    def replace(self, config: CobraConfig) -> None:
        self._config = config

    def active_profile(self) -> ProfileConfig:
        return self._config.active()

    def model(self) -> ModelConfig:
        return self.active_profile().model

    def storage(self) -> StorageConfig:
        return self.active_profile().storage

    def storage_paths(self) -> dict[str, Path]:
        return self.storage().expand()

    def mcp_servers(self) -> list[McpServerEntry]:
        return list(self.active_profile().mcp_servers)

    def api_key(self, provider: str) -> str:
        keys = self.active_profile().api_keys
        if provider == "claude":
            value = keys.claude
        elif provider == "copilot":
            value = keys.copilot
        else:
            raise KeyError(f"Unknown API key provider: {provider}")
        if not value.strip():
            raise KeyError(f"Missing API key for {provider}")
        return value

    def require(self, *path: str):
        node: object = self._config.model_dump()
        for part in path:
            if not isinstance(node, dict) or part not in node:
                raise KeyError(".".join(path))
            node = node[part]
        return node
