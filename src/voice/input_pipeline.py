"""Voice input pipeline I1–I5."""

from __future__ import annotations

from collections.abc import Callable

from voice.config import VoiceConfig
from voice.models import TranscriptionResult
from voice.mood import MoodInferencer


class VoiceInputPipeline:
    """Capture → transcribe → confidence check → handoff to brain."""

    def __init__(
        self,
        config: VoiceConfig,
        *,
        transcribe: Callable[[bytes], tuple[str, float]] | None = None,
        on_low_confidence: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self._transcribe = transcribe or self._default_transcribe
        self._on_low_confidence = on_low_confidence
        self.mood = MoodInferencer()

    def process_audio(self, audio: bytes) -> TranscriptionResult | None:
        text, confidence = self._transcribe(audio)
        mood = self.mood.infer_from_text_proxy(text, confidence=confidence)
        result = TranscriptionResult(text=text, confidence=confidence, mood=mood)
        if not result.acceptable:
            if self.config.audio_cue and self._on_low_confidence:
                self._on_low_confidence()
            return None
        return result

    def process_text(self, text: str, *, confidence: float = 1.0) -> TranscriptionResult | None:
        """Dev/test path when microphone audio is unavailable."""

        mood = self.mood.infer_from_text_proxy(text, confidence=confidence)
        result = TranscriptionResult(text=text, confidence=confidence, mood=mood)
        threshold = self.config.confidence_threshold
        if not text.strip() or confidence < threshold:
            if self.config.audio_cue and self._on_low_confidence:
                self._on_low_confidence()
            return None
        return result

    @staticmethod
    def _default_transcribe(audio: bytes) -> tuple[str, float]:
        if not audio:
            return "", 0.0
        try:
            decoded = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            return "", 0.0
        return decoded, 0.9 if decoded else 0.0
