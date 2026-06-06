"""Voice output O1–O4 and cloned model management."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union

from voice.config import VoiceConfig
from voice.models import MoodResult, VoiceModelStatus

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
    ) -> None:
        self.config = config
        self._on_text = on_text
        self._on_speech = on_speech

    def model_status(self) -> VoiceModelStatus:
        marker = self.config.model_marker_path
        if marker.exists():
            return VoiceModelStatus(ready=True, path=str(self.config.voice_model_path))
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
        if self.config.output_mode in {"both", "voice"} and status.ready and self._on_speech:
            self._on_speech(text, rate)

    def mark_model_ready(self) -> None:
        self.config.voice_model_path.mkdir(parents=True, exist_ok=True)
        self.config.model_marker_path.write_text("ready\n", encoding="utf-8")

    def remove_model(self) -> None:
        if self.config.model_marker_path.exists():
            self.config.model_marker_path.unlink()
