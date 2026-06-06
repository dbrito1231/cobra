"""Voice configuration per voice/configuration.md."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VOICE_DIR = Path.home() / ".cobra" / "voice"
DEFAULT_SESSION_END = "That's all for now C.O.B.R.A."
DEFAULT_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class VoiceConfig:
    wake_word: str = "cobra"
    session_end_phrase: str = DEFAULT_SESSION_END
    audio_cue: bool = True
    tts_model: str = "xtts"
    voice_model_path: Path = DEFAULT_VOICE_DIR
    speaking_speed_adaptation: bool = True
    output_mode: str = "both"
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD

    @classmethod
    def from_env(cls) -> VoiceConfig:
        return cls(
            wake_word=os.environ.get("COBRA_WAKE_WORD", "cobra"),
            session_end_phrase=os.environ.get(
                "COBRA_SESSION_END", DEFAULT_SESSION_END
            ),
            voice_model_path=Path(
                os.environ.get("COBRA_VOICE_MODEL_PATH", DEFAULT_VOICE_DIR)
            ),
        )

    @classmethod
    def from_config_dict(cls, data: dict) -> VoiceConfig:
        voice = data.get("voice") or {}
        return cls(
            wake_word=str(voice.get("wake_word", "cobra")),
            session_end_phrase=str(
                voice.get("session_end_phrase", DEFAULT_SESSION_END)
            ),
            audio_cue=bool(voice.get("audio_cue", True)),
            tts_model=str(voice.get("tts_model", "xtts")),
            voice_model_path=Path(
                os.path.expanduser(
                    voice.get("voice_model_path", str(DEFAULT_VOICE_DIR))
                )
            ),
            speaking_speed_adaptation=bool(
                voice.get("speaking_speed_adaptation", True)
            ),
            output_mode=str(voice.get("output_mode", "both")),
            confidence_threshold=float(
                voice.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
            ),
        )

    @property
    def model_marker_path(self) -> Path:
        return self.voice_model_path / "model.ready"
