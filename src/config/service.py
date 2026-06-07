"""Configuration service — load, validate, profiles, hot reload, backup."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import os

from config.backup import backup_config, list_backups, restore_backup
from config.hot_reload import HotReloadWatcher
from config.loader import (
    DEFAULT_CONFIG_PATH,
    config_to_legacy_dict,
    load_config,
    save_config,
)
from config.models import CobraConfig, HealthStatus, ValidationReport
from config.profiles import ProfileManager
from config.reader import ConfigReader
from config.validation import validate_config
from config.wizard import WizardInput, run_wizard


class ConfigService:
    """Top-level Configuration component initialized in Orchestrator Phase 1."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH).expanduser()
        self.config: CobraConfig | None = None
        self.reader = ConfigReader(CobraConfig())
        self._initialized = False
        self._needs_wizard = False
        self._on_config_applied: Callable[[CobraConfig], None] | None = None
        self._on_notify: Callable[[str], None] | None = None
        self._on_reverted: Callable[[str], None] | None = None
        self._hot_reload = HotReloadWatcher(
            config_path=self.config_path,
            on_applied=self._apply_hot_reload,
            on_notify=lambda msg: self._on_notify(msg) if self._on_notify else None,
            on_reverted=lambda msg: self._on_reverted(msg) if self._on_reverted else None,
        )

    def set_on_config_applied(self, callback: Callable[[CobraConfig], None]) -> None:
        self._on_config_applied = callback

    def set_notify_handlers(
        self,
        *,
        on_notify: Callable[[str], None] | None = None,
        on_reverted: Callable[[str], None] | None = None,
    ) -> None:
        self._on_notify = on_notify
        self._on_reverted = on_reverted

    @property
    def needs_wizard(self) -> bool:
        return self._needs_wizard

    def initialize(self) -> ValidationReport:
        """Load config, validate, and start hot reload."""

        if not self.config_path.exists():
            self._needs_wizard = True
            self._initialized = True
            return ValidationReport(checks=[])

        self.config = load_config(self.config_path)
        self.reader.replace(self.config)
        report = validate_config(self.config, config_path=self.config_path)
        if report.passed:
            self._hot_reload.start(self.config)
            self._initialized = True
            self._needs_wizard = False
        return report

    def complete_wizard(self, data: WizardInput) -> ValidationReport:
        """Run first-time or re-run wizard and reload configuration."""

        self.config = run_wizard(
            data,
            config_path=self.config_path,
            skip_lm_studio=os.environ.get("COBRA_SKIP_LM_STUDIO", "0") == "1",
        )
        self.reader.replace(self.config)
        report = validate_config(
            self.config,
            config_path=self.config_path,
            skip_lm_studio=False,
        )
        if report.passed:
            self._needs_wizard = False
            self._initialized = True
            self._hot_reload.start(self.config)
            self._notify_applied(self.config)
        return report

    def shutdown(self) -> None:
        self._hot_reload.stop()
        if self.config is not None:
            save_config(self.config, self.config_path)
        self._initialized = False

    def reload(self) -> ValidationReport:
        self.config = load_config(self.config_path)
        self.reader.replace(self.config)
        report = validate_config(self.config, config_path=self.config_path)
        if report.passed:
            self._notify_applied(self.config)
        return report

    def switch_profile(self, profile_id: str) -> ValidationReport:
        if self.config is None:
            raise RuntimeError("Config not loaded")
        manager = ProfileManager(self.config)
        self.config = manager.switch(profile_id)
        self.reader.replace(self.config)
        save_config(self.config, self.config_path)
        report = validate_config(self.config, config_path=self.config_path)
        if report.passed:
            self._notify_applied(self.config)
        return report

    def create_backup(self) -> Path:
        if self.config is None:
            raise RuntimeError("Config not loaded")
        return backup_config(self.config)

    def restore(self, backup_path: Path) -> ValidationReport:
        self.config = restore_backup(backup_path, self.config_path)
        self.reader.replace(self.config)
        report = validate_config(self.config, config_path=self.config_path)
        if report.passed:
            self._initialized = True
            self._notify_applied(self.config)
        return report

    def list_backups(self) -> list[Path]:
        if self.config is None:
            return []
        return list_backups(self.config.active().storage.expand()["backups_dir"])

    def to_legacy_dict(self) -> dict:
        if self.config is None:
            return {}
        return config_to_legacy_dict(self.config)

    def health(self) -> HealthStatus:
        if self._needs_wizard:
            return HealthStatus(healthy=True, message="setup wizard required", degraded=True)
        if not self._initialized or self.config is None:
            return HealthStatus(healthy=False, message="not initialized")
        return HealthStatus(healthy=True)

    def _apply_hot_reload(self, config: CobraConfig) -> None:
        self.config = config
        self.reader.replace(config)
        self._notify_applied(config)

    def _notify_applied(self, config: CobraConfig) -> None:
        if self._on_config_applied is not None:
            self._on_config_applied(config)
