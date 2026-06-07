"""First-time setup wizard W1–W10 (programmatic API)."""

from __future__ import annotations

from dataclasses import dataclass, field

from config.loader import save_config
from config.models import ApiKeys, CobraConfig, McpServerEntry, ModelConfig, ProfileConfig, StorageConfig
from config.validation import validate_config


@dataclass
class WizardInput:
    model_endpoint: str = "http://127.0.0.1:1234"
    model_id: str = ""
    claude_api_key: str = ""
    copilot_api_key: str = ""
    profile_name: str = "default"
    display_name: str = "Default"
    wiki_dir: str = "~/.cobra/wiki/"
    memory_dir: str = "~/.cobra/memory/"
    logs_dir: str = "~/.cobra/logs/"
    backups_dir: str = "~/.cobra/backups/"
    mcp_servers: list[McpServerEntry] = field(default_factory=list)


def run_wizard(
    data: WizardInput,
    *,
    config_path=None,
    skip_lm_studio: bool = False,
) -> CobraConfig:
    """Write a new config from wizard inputs after validation."""

    profile = ProfileConfig(
        name=data.display_name,
        model=ModelConfig(
            endpoint=data.model_endpoint,
            model_id=data.model_id,
        ),
        api_keys=ApiKeys(claude=data.claude_api_key, copilot=data.copilot_api_key),
        storage=StorageConfig(
            wiki_dir=data.wiki_dir,
            memory_dir=data.memory_dir,
            logs_dir=data.logs_dir,
            backups_dir=data.backups_dir,
        ),
        mcp_servers=data.mcp_servers,
    )
    config = CobraConfig(active_profile=data.profile_name, profiles={data.profile_name: profile})
    report = validate_config(
        config,
        config_path=config_path,
        skip_lm_studio=skip_lm_studio,
        require_file_exists=False,
    )
    if not report.passed:
        failures = "; ".join(check.message for check in report.failures())
        raise ValueError(f"Wizard validation failed: {failures}")
    save_config(config, config_path)
    return config
