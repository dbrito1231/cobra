"""Profile switching P3–P5."""

from __future__ import annotations

from config.loader import save_config
from config.models import CobraConfig, ProfileConfig
from config.validation import validate_config


class ProfileManager:
    """Switch active profile with immediate re-validation."""

    def __init__(self, config: CobraConfig) -> None:
        self.config = config

    def list_profiles(self) -> list[str]:
        return list(self.config.profiles.keys())

    def switch(self, profile_id: str) -> CobraConfig:
        if profile_id not in self.config.profiles:
            raise KeyError(f"Profile '{profile_id}' not found")
        self.config.active_profile = profile_id
        report = validate_config(self.config)
        if not report.passed:
            failures = "; ".join(check.message for check in report.failures())
            raise ValueError(f"Profile validation failed: {failures}")
        return self.config

    def set_default(self, profile_id: str) -> CobraConfig:
        self.config = self.switch(profile_id)
        save_config(self.config)
        return self.config

    def add_profile(self, profile_id: str, profile: ProfileConfig) -> None:
        self.config.profiles[profile_id] = profile
