"""Tests for the Configuration component."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.backup import backup_config, list_backups, restore_backup
from config.loader import default_config, load_config, save_config
from config.models import CobraConfig, McpServerEntry, ProfileConfig
from config.profiles import ProfileManager
from config.service import ConfigService
from config.validation import validate_config
from config.wizard import WizardInput, run_wizard


@pytest.fixture
def sample_config() -> CobraConfig:
    profile = ProfileConfig(
        name="Default",
        api_keys={"claude": "sk-test-claude-key", "copilot": "copilot-test-key"},
        model={"provider": "lm_studio", "endpoint": "http://127.0.0.1:1234", "model_id": "test-model"},
    )
    return CobraConfig(active_profile="default", profiles={"default": profile})


class TestConfigLoader:
    def test_round_trip(self, tmp_path: Path, sample_config: CobraConfig) -> None:
        path = tmp_path / "config.yaml"
        save_config(sample_config, path)
        loaded = load_config(path)
        assert loaded.active_profile == "default"
        assert loaded.active().model.model_id == "test-model"


class TestValidation:
    def test_validation_passes_with_skip_lm(self, tmp_path: Path, sample_config: CobraConfig) -> None:
        wiki = tmp_path / "wiki"
        memory = tmp_path / "memory"
        sample_config.profiles["default"].storage.wiki_dir = str(wiki)
        sample_config.profiles["default"].storage.memory_dir = str(memory)
        report = validate_config(sample_config, skip_lm_studio=True)
        assert report.passed

    def test_missing_api_key_fails(self, sample_config: CobraConfig) -> None:
        sample_config.profiles["default"].api_keys.claude = ""
        report = validate_config(sample_config, skip_lm_studio=True)
        assert not report.passed
        assert any(check.code == "V5" for check in report.failures())


class TestProfiles:
    def test_switch_profile(self, tmp_path: Path, sample_config: CobraConfig) -> None:
        sample_config.profiles["default"].storage.wiki_dir = str(tmp_path / "wiki")
        sample_config.profiles["default"].storage.memory_dir = str(tmp_path / "memory")
        sample_config.profiles["work"] = ProfileConfig(
            name="Work",
            api_keys={"claude": "sk-test-claude-key", "copilot": "copilot-test-key"},
            storage=sample_config.profiles["default"].storage,
        )
        manager = ProfileManager(sample_config)
        manager.switch("work")
        assert sample_config.active_profile == "work"


class TestWizard:
    def test_run_wizard_writes_config(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        config = run_wizard(
            WizardInput(
                claude_api_key="sk-test-claude-key",
                copilot_api_key="copilot-test-key",
                wiki_dir=str(tmp_path / "wiki"),
                memory_dir=str(tmp_path / "memory"),
            ),
            config_path=path,
            skip_lm_studio=True,
        )
        assert path.exists()
        assert config.active_profile == "default"


class TestBackupRestore:
    def test_backup_and_restore(self, tmp_path: Path, sample_config: CobraConfig) -> None:
        backups = tmp_path / "backups"
        sample_config.profiles["default"].storage.backups_dir = str(backups)
        backup_path = backup_config(sample_config)
        assert backup_path.exists()
        assert backup_path in list_backups(backups)

        target = tmp_path / "config.yaml"
        save_config(default_config(), target)
        restored = restore_backup(backup_path, target)
        assert restored.active().model.model_id == sample_config.active().model.model_id


class TestConfigService:
    def test_initialize_from_dict(self, tmp_path: Path) -> None:
        service = ConfigService(tmp_path / "config.yaml")
        config_dict = {
            "version": "1.0",
            "active_profile": "default",
            "profiles": {
                "default": {
                    "name": "Default",
                    "model": {
                        "provider": "lm_studio",
                        "endpoint": "http://127.0.0.1:1234",
                        "model_id": "test",
                    },
                    "api_keys": {
                        "claude": "sk-test-claude-key",
                        "copilot": "copilot-test-key",
                    },
                    "storage": {
                        "wiki_dir": str(tmp_path / "wiki"),
                        "memory_dir": str(tmp_path / "memory"),
                        "logs_dir": str(tmp_path / "logs"),
                        "backups_dir": str(tmp_path / "backups"),
                    },
                }
            },
        }
        service.config = CobraConfig.from_dict(config_dict)
        service.reader.replace(service.config)
        report = validate_config(service.config, skip_lm_studio=True)
        service._initialized = report.passed
        assert report.passed
        assert service.health().healthy
