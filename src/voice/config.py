"""Voice configuration per voice/configuration.md."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VOICE_DIR = Path.home() / ".cobra" / "voice"
DEFAULT_SESSION_END = "That's all for now C.O.B.R.A."
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_SAMPLE_RATE = 16000


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
    whisper_model: str = DEFAULT_WHISPER_MODEL
    whisper_model_path: Path | None = None
    openwakeword_model: str = "hey_jarvis"
    sample_rate: int = DEFAULT_SAMPLE_RATE
    audio_cue_path: Path | None = None

    @classmethod
    def from_env(cls) -> VoiceConfig:
        whisper_path = os.environ.get("COBRA_WHISPER_MODEL_PATH")
        cue_path = os.environ.get("COBRA_AUDIO_CUE_PATH")
        return cls(
            wake_word=os.environ.get("COBRA_WAKE_WORD", "cobra"),
            session_end_phrase=os.environ.get(
                "COBRA_SESSION_END", DEFAULT_SESSION_END
            ),
            voice_model_path=Path(
                os.environ.get("COBRA_VOICE_MODEL_PATH", DEFAULT_VOICE_DIR)
            ),
            whisper_model=os.environ.get("COBRA_WHISPER_MODEL", DEFAULT_WHISPER_MODEL),
            whisper_model_path=Path(whisper_path) if whisper_path else None,
            openwakeword_model=os.environ.get(
                "COBRA_OPENWAKEWORD_MODEL", "hey_jarvis"
            ),
            sample_rate=int(os.environ.get("COBRA_SAMPLE_RATE", DEFAULT_SAMPLE_RATE)),
            audio_cue_path=Path(cue_path) if cue_path else None,
        )

    @classmethod
    def from_config_dict(cls, data: dict) -> VoiceConfig:
        voice = data.get("voice") or {}
        whisper_path = voice.get("whisper_model_path")
        cue_path = voice.get("audio_cue_path")
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
            whisper_model=str(voice.get("whisper_model", DEFAULT_WHISPER_MODEL)),
            whisper_model_path=(
                Path(os.path.expanduser(whisper_path)) if whisper_path else None
            ),
            openwakeword_model=str(
                voice.get("openwakeword_model", "hey_jarvis")
            ),
            sample_rate=int(voice.get("sample_rate", DEFAULT_SAMPLE_RATE)),
            audio_cue_path=Path(os.path.expanduser(cue_path)) if cue_path else None,
        )

    @property
    def model_marker_path(self) -> Path:
        return self.voice_model_path / "model.ready"

    @property
    def speaker_wav_path(self) -> Path:
        """Reference speaker clip for XTTS cloning/inference."""

        return self.voice_model_path / "speaker.wav"

    @property
    def xtts_model_dir(self) -> Path:
        return self.voice_model_path / "xtts"
