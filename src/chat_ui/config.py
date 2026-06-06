"""Chat UI configuration with defaults until the config agent is available."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_UI_PORT = 8765
DEFAULT_WIKI_DIR = Path.home() / ".cobra" / "wiki"
DEFAULT_SESSIONS_DIR = Path.home() / ".cobra" / "logs" / "sessions"
DEFAULT_PROFILE_NAME = "Default"
PIPELINE_SLOW_THRESHOLD_SECONDS = 3.0


@dataclass(frozen=True)
class ChatUIConfig:
    """Resolved settings for the Chat UI server."""

    host: str = "127.0.0.1"
    port: int = DEFAULT_UI_PORT
    wiki_dir: Path = DEFAULT_WIKI_DIR
    sessions_dir: Path = DEFAULT_SESSIONS_DIR
    profile_name: str = DEFAULT_PROFILE_NAME
    open_browser: bool = True

    @classmethod
    def from_env(cls) -> "ChatUIConfig":
        return cls(
            host=os.environ.get("COBRA_UI_HOST", "127.0.0.1"),
            port=int(os.environ.get("COBRA_UI_PORT", DEFAULT_UI_PORT)),
            wiki_dir=Path(os.environ.get("COBRA_WIKI_DIR", DEFAULT_WIKI_DIR)),
            sessions_dir=Path(
                os.environ.get("COBRA_SESSIONS_DIR", DEFAULT_SESSIONS_DIR)
            ),
            profile_name=os.environ.get("COBRA_PROFILE_NAME", DEFAULT_PROFILE_NAME),
            open_browser=os.environ.get("COBRA_UI_OPEN_BROWSER", "1") == "1",
        )

    @classmethod
    def from_config_dict(cls, data: dict) -> "ChatUIConfig":
        """Build from a future config reader API payload."""
        ui = data.get("ui") or {}
        storage = data.get("storage") or {}
        profiles = data.get("profiles") or {}
        active = data.get("active_profile", "default")
        profile = profiles.get(active) or {}
        profile_storage = profile.get("storage") or {}

        wiki_dir = profile_storage.get("wiki_dir") or storage.get(
            "wiki_dir", str(DEFAULT_WIKI_DIR)
        )
        sessions_dir = profile_storage.get("logs_dir") or storage.get(
            "logs_dir", str(DEFAULT_SESSIONS_DIR.parent)
        )

        return cls(
            host=ui.get("host", "127.0.0.1"),
            port=int(ui.get("port", DEFAULT_UI_PORT)),
            wiki_dir=Path(os.path.expanduser(wiki_dir)),
            sessions_dir=Path(os.path.expanduser(sessions_dir)) / "sessions",
            profile_name=profile.get("name", DEFAULT_PROFILE_NAME),
            open_browser=bool(ui.get("open_browser", True)),
        )
