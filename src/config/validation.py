"""Startup validation V1–V9."""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx

from config.loader import DEFAULT_CONFIG_PATH
from config.models import CobraConfig, ValidationCheck, ValidationReport

API_KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{8,}$|^copilot-[A-Za-z0-9_-]{8,}$|^.{8,}$")


def validate_config(
    config: CobraConfig,
    *,
    config_path: Path | None = None,
    skip_lm_studio: bool | None = None,
    require_file_exists: bool = True,
) -> ValidationReport:
    """Run all startup validation checks in order."""

    checks: list[ValidationCheck] = []
    path = Path(config_path or DEFAULT_CONFIG_PATH).expanduser()
    skip_lm = (
        skip_lm_studio
        if skip_lm_studio is not None
        else os.environ.get("COBRA_SKIP_LM_STUDIO", "0") == "1"
    )

    if require_file_exists:
        checks.append(_check_readable(path))
    else:
        checks.append(
            ValidationCheck(code="V1", passed=True, message="New config pending write")
        )
    checks.append(_check_required_fields(config))
    if not skip_lm:
        checks.extend(_check_lm_studio(config))
    else:
        checks.append(ValidationCheck(code="V3", passed=True, message="LM Studio check skipped"))
        checks.append(ValidationCheck(code="V4", passed=True, message="Model check skipped"))
    checks.append(_check_api_key("V5", "claude", config.active().api_keys.claude))
    checks.append(_check_api_key("V6", "copilot", config.active().api_keys.copilot))
    checks.extend(_check_storage(config))
    checks.append(_check_active_profile(config))
    return ValidationReport(checks=checks)


def _check_readable(path: Path) -> ValidationCheck:
    if not path.exists():
        return ValidationCheck(
            code="V1",
            passed=False,
            message=f"Config file missing at {path}. Run setup wizard or create config.yaml.",
        )
    try:
        path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationCheck(code="V1", passed=False, message=f"Config unreadable: {exc}")
    return ValidationCheck(code="V1", passed=True, message="Config file readable")


def _check_required_fields(config: CobraConfig) -> ValidationCheck:
    try:
        profile = config.active()
    except KeyError as exc:
        return ValidationCheck(code="V2", passed=False, message=str(exc))
    if not profile.model.endpoint:
        return ValidationCheck(
            code="V2",
            passed=False,
            message="Missing required field: model.endpoint",
        )
    return ValidationCheck(code="V2", passed=True, message="Required fields present")


def _check_lm_studio(config: CobraConfig) -> list[ValidationCheck]:
    endpoint = config.active().model.endpoint.rstrip("/")
    try:
        response = httpx.get(f"{endpoint}/v1/models", timeout=3.0)
        if response.status_code != 200:
            return [
                ValidationCheck(
                    code="V3",
                    passed=False,
                    message=f"LM Studio unreachable at {endpoint} (HTTP {response.status_code})",
                ),
                ValidationCheck(code="V4", passed=False, message="Model not verified"),
            ]
    except Exception as exc:
        return [
            ValidationCheck(
                code="V3",
                passed=False,
                message=f"LM Studio unreachable at {endpoint}: {exc}",
            ),
            ValidationCheck(code="V4", passed=False, message="Model not verified"),
        ]

    model_id = config.active().model.model_id
    if not model_id:
        return [
            ValidationCheck(code="V3", passed=True, message="LM Studio reachable"),
            ValidationCheck(
                code="V4",
                passed=False,
                message="No model_id configured. Set model.model_id in config.",
            ),
        ]

    try:
        payload = response.json()
        models = payload.get("data") or payload.get("models") or []
        ids = {item.get("id") for item in models if isinstance(item, dict)}
        if model_id not in ids and ids:
            return [
                ValidationCheck(code="V3", passed=True, message="LM Studio reachable"),
                ValidationCheck(
                    code="V4",
                    passed=False,
                    message=f"Model '{model_id}' not loaded in LM Studio.",
                ),
            ]
    except Exception:
        pass

    return [
        ValidationCheck(code="V3", passed=True, message="LM Studio reachable"),
        ValidationCheck(code="V4", passed=True, message="Model loaded and ready"),
    ]


def _check_api_key(code: str, name: str, value: str) -> ValidationCheck:
    if not value.strip():
        return ValidationCheck(
            code=code,
            passed=False,
            message=f"{name.title()} API key missing in active profile.",
        )
    if not API_KEY_PATTERN.match(value.strip()):
        return ValidationCheck(
            code=code,
            passed=False,
            message=f"{name.title()} API key format looks invalid.",
        )
    return ValidationCheck(code=code, passed=True, message=f"{name.title()} API key present")


def _check_storage(config: CobraConfig) -> list[ValidationCheck]:
    storage = config.active().storage.expand()
    checks: list[ValidationCheck] = []
    for code, key in (("V7", "wiki_dir"), ("V8", "memory_dir")):
        path = storage[key]
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            checks.append(
                ValidationCheck(code=code, passed=True, message=f"{key} writable")
            )
        except OSError as exc:
            checks.append(
                ValidationCheck(
                    code=code,
                    passed=False,
                    message=f"{key} not writable at {path}: {exc}",
                )
            )
    return checks


def _check_active_profile(config: CobraConfig) -> ValidationCheck:
    if config.active_profile not in config.profiles:
        return ValidationCheck(
            code="V9",
            passed=False,
            message=f"Active profile '{config.active_profile}' does not exist.",
        )
    return ValidationCheck(code="V9", passed=True, message="Active profile exists")
