"""Tools component configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tools.models import ToolCall

_SANDBOX_DEFAULT: bool = True
_SESSION_SANDBOX: bool | None = None


def configure_sandbox_default(enabled: bool) -> None:
    """Set the profile-level sandbox default used when no session override is active."""

    global _SANDBOX_DEFAULT
    _SANDBOX_DEFAULT = enabled


def set_session_sandbox_override(enabled: bool | None) -> None:
    """Per-session sandbox override (sandboxing.md §5.2)."""

    global _SESSION_SANDBOX
    _SESSION_SANDBOX = enabled


def reset_session_sandbox() -> None:
    """Clear per-session override so the profile default applies."""

    set_session_sandbox_override(None)


def sandbox_enabled_for_call(call: ToolCall) -> bool:
    """Resolve whether a call should run sandboxed."""

    if _SESSION_SANDBOX is not None:
        return _SESSION_SANDBOX
    return call.sandboxed


@dataclass
class ToolsConfig:
    wiki_dir: Path
    logs_dir: Path
    sandbox_default: bool = True
    session_sandbox: bool | None = None

    @classmethod
    def from_config_dict(cls, data: dict) -> ToolsConfig:
        storage = data.get("storage") or {}
        sandbox = bool(data.get("tool_sandbox", True))
        return cls(
            wiki_dir=Path(os.path.expanduser(storage.get("wiki_dir", "~/.cobra/wiki"))),
            logs_dir=Path(os.path.expanduser(storage.get("logs_dir", "~/.cobra/logs"))),
            sandbox_default=sandbox,
        )

    @property
    def sandbox_enabled(self) -> bool:
        if self.session_sandbox is not None:
            return self.session_sandbox
        return self.sandbox_default
