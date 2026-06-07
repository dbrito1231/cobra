"""Brain-specific configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrainConfig:
    wiki_dir: Path
    memory_dir: Path
    logs_dir: Path
    model_endpoint: str = "http://127.0.0.1:1234"
    model_id: str = ""
    claude_api_key: str = ""
    copilot_api_key: str = ""
    router_confidence_threshold: float = 0.7
    verification_timeout_seconds: float = 10.0
    offline_mode: bool = False

    @classmethod
    def from_config_dict(cls, data: dict) -> BrainConfig:
        storage = data.get("storage") or {}
        model = data.get("model") or {}
        keys = data.get("api_keys") or {}
        return cls(
            wiki_dir=Path(os.path.expanduser(storage.get("wiki_dir", "~/.cobra/wiki"))),
            memory_dir=Path(os.path.expanduser(storage.get("memory_dir", "~/.cobra/memory"))),
            logs_dir=Path(os.path.expanduser(storage.get("logs_dir", "~/.cobra/logs"))),
            model_endpoint=str(model.get("endpoint", "http://127.0.0.1:1234")),
            model_id=str(model.get("model_id", "")),
            claude_api_key=str(keys.get("claude", "")),
            copilot_api_key=str(keys.get("copilot", "")),
            offline_mode=os.environ.get("COBRA_BRAIN_OFFLINE", "0") == "1",
        )
