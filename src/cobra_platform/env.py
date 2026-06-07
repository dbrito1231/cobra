"""Shared subprocess environment helpers."""

from __future__ import annotations

import os


def user_home_env() -> dict[str, str]:
    """Return HOME and USERPROFILE for cross-platform subprocess env."""

    env: dict[str, str] = {}
    home = os.environ.get("HOME")
    profile = os.environ.get("USERPROFILE")
    if home:
        env["HOME"] = home
    if profile:
        env["USERPROFILE"] = profile
    if home and not profile:
        env["USERPROFILE"] = home
    if profile and not home:
        env["HOME"] = profile
    return env


def merge_subprocess_env(*, path: str = "", pythonpath: str = "", extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a minimal subprocess environment with cross-platform home vars."""

    env = {
        "PATH": path or os.environ.get("PATH", ""),
        **user_home_env(),
    }
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    if extra:
        env.update(extra)
    return {key: value for key, value in env.items() if value}
