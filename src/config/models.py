"""Configuration data models per config-file-structure.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


DEFAULT_VERSION = "1.0"
SUPPORTED_MCP_PROTOCOL = "1.0"


class ModelConfig(BaseModel):
    provider: str = "lm_studio"
    endpoint: str = "http://127.0.0.1:1234"
    model_id: str = ""


class ApiKeys(BaseModel):
    claude: str = ""
    copilot: str = ""


class StorageConfig(BaseModel):
    wiki_dir: str = "~/.cobra/wiki/"
    memory_dir: str = "~/.cobra/memory/"
    logs_dir: str = "~/.cobra/logs/"
    backups_dir: str = "~/.cobra/backups/"

    def expand(self) -> dict[str, Path]:
        return {key: Path(str(value)).expanduser() for key, value in self.model_dump().items()}


class McpServerEntry(BaseModel):
    name: str
    endpoint: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True
    priority: int = 0


class ProfileConfig(BaseModel):
    name: str = "Default"
    model: ModelConfig = Field(default_factory=ModelConfig)
    api_keys: ApiKeys = Field(default_factory=ApiKeys)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    mcp_servers: list[McpServerEntry] = Field(default_factory=list)
    personality_mode: str = "default"
    tool_sandbox: bool = True
    voice: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)


class CobraConfig(BaseModel):
    version: str = DEFAULT_VERSION
    active_profile: str = "default"
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    ui: dict[str, Any] = Field(default_factory=dict)

    @field_validator("profiles")
    @classmethod
    def require_profiles(cls, value: dict[str, ProfileConfig]) -> dict[str, ProfileConfig]:
        if not value:
            return {"default": ProfileConfig()}
        return value

    def active(self) -> ProfileConfig:
        profile = self.profiles.get(self.active_profile)
        if profile is None:
            raise KeyError(f"Active profile '{self.active_profile}' not found")
        return profile

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CobraConfig:
        return cls.model_validate(data)


class ValidationCheck(BaseModel):
    code: str
    passed: bool
    message: str


class ValidationReport(BaseModel):
    checks: list[ValidationCheck] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def lm_studio_unreachable(self) -> bool:
        return any(
            check.code in {"V3", "V4"} and not check.passed for check in self.checks
        )

    def failures(self) -> list[ValidationCheck]:
        return [check for check in self.checks if not check.passed]


class HealthStatus(BaseModel):
    healthy: bool = True
    message: str = "ok"
    degraded: bool = False
