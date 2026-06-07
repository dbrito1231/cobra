"""Voice output O1–O4 and cloned model management."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union

from voice.config import VoiceConfig
from voice.models import MoodResult, VoiceModelStatus
from voice.tts import TTSSynthesizer

OutputHandler = Callable[
    [str, MoodResult], Union[Awaitable[None], None]
]


class VoiceOutput:
    """Dual voice + text output using local cloned model when available."""

    def __init__(
        self,
        config: VoiceConfig,
        *,
        on_text: OutputHandler | None = None,
        on_speech: Callable[[str, float], None] | None = None,
        on_audio: Callable[[bytes], None] | None = None,
        synthesizer: TTSSynthesizer | None = None,
    ) -> None:
        self.config = config
        self._on_text = on_text
        self._on_speech = on_speech
        self._on_audio = on_audio
        self._synthesizer = synthesizer or TTSSynthesizer(config)

    @property
    def tts_backend(self) -> str:
        return self._synthesizer.backend

    def model_status(self) -> VoiceModelStatus:
        marker = self.config.model_marker_path
        speaker = self.config.speaker_wav_path
        if marker.exists() and speaker.exists():
            return VoiceModelStatus(ready=True, path=str(self.config.voice_model_path))
        if marker.exists() and not speaker.exists():
            return VoiceModelStatus(
                ready=False,
                path=str(self.config.voice_model_path),
                message="Voice model marker present but speaker clip missing",
            )
        return VoiceModelStatus(
            ready=False,
            path=str(self.config.voice_model_path),
            message="Voice model missing — text-only output until cloning completes",
        )

    def speaking_rate(self, mood: MoodResult) -> float:
        if not self.config.speaking_speed_adaptation:
            return 1.0
        return mood.speaking_rate

    async def deliver(self, text: str, mood: MoodResult | None = None) -> None:
        mood = mood or MoodResult()
        rate = self.speaking_rate(mood)

        if self.config.output_mode in {"both", "text"} and self._on_text:
            result = self._on_text(text, mood)
            if hasattr(result, "__await__"):
                await result

        status = self.model_status()
        voice_requested = self.config.output_mode in {"both", "voice"}
        if not voice_requested or not status.ready:
            return

        audio = self._synthesizer.synthesize(text, rate=rate)
        if audio and self._on_audio:
            self._on_audio(audio)
        elif self._on_speech:
            self._on_speech(text, rate)

    def mark_model_ready(self) -> None:
        self.config.voice_model_path.mkdir(parents=True, exist_ok=True)
        self.config.model_marker_path.write_text("ready\n", encoding="utf-8")
        if not self.config.speaker_wav_path.exists():
            self.config.speaker_wav_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    def remove_model(self) -> None:
        if self.config.model_marker_path.exists():
            self.config.model_marker_path.unlink()
        if self.config.speaker_wav_path.exists():
            self.config.speaker_wav_path.unlink()
