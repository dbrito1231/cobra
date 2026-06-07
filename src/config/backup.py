"""Manual local backup and restore BK1–BK9."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from config.loader import DEFAULT_CONFIG_PATH, load_config, save_config
from config.models import CobraConfig
from config.validation import validate_config

MAX_BACKUPS = 20


def backup_config(config: CobraConfig, backups_dir: Path | None = None) -> Path:
    """Create timestamped backup under ~/.cobra/backups/."""

    storage = config.active().storage.expand()
    target_dir = Path(backups_dir or storage["backups_dir"])
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = target_dir / f"config-{stamp}.yaml"
    backup_path.write_text(
        yaml.safe_dump(config.model_dump(mode="python"), sort_keys=False),
        encoding="utf-8",
    )
    _prune_old_backups(target_dir)
    return backup_path


def list_backups(backups_dir: Path) -> list[Path]:
    return sorted(backups_dir.glob("config-*.yaml"), reverse=True)


def restore_backup(backup_path: Path, config_path: Path | None = None) -> CobraConfig:
    """Validate and apply a backup file."""

    raw = yaml.safe_load(Path(backup_path).read_text(encoding="utf-8")) or {}
    candidate = CobraConfig.from_dict(raw)
    report = validate_config(candidate)
    if not report.passed:
        failures = "; ".join(check.message for check in report.failures())
        raise ValueError(f"Backup invalid: {failures}")
    save_config(candidate, config_path or DEFAULT_CONFIG_PATH)
    return candidate


def _prune_old_backups(backups_dir: Path) -> None:
    backups = list_backups(backups_dir)
    for stale in backups[MAX_BACKUPS:]:
        stale.unlink(missing_ok=True)
