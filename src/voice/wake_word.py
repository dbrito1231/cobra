"""Wake word detection and session end phrase handling."""

from __future__ import annotations

import re
from collections.abc import Callable

from voice.audio_utils import bytes_to_float32
from voice.config import VoiceConfig

try:
    from openwakeword.model import Model as OpenWakeWordModel

    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    OpenWakeWordModel = None  # type: ignore[misc, assignment]


class OpenWakeWordBackend:
    """Optional audio-based wake word detection via openwakeword."""

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._model: OpenWakeWordModel | None = None

    @property
    def available(self) -> bool:
        return OPENWAKEWORD_AVAILABLE

    def _ensure_model(self) -> OpenWakeWordModel | None:
        if not OPENWAKEWORD_AVAILABLE:
            return None
        if self._model is None:
            self._model = OpenWakeWordModel(
                wakeword_models=[self.config.openwakeword_model],
            )
        return self._model

    def detect(self, audio: bytes) -> bool:
        model = self._ensure_model()
        if model is None:
            return False

        samples = bytes_to_float32(audio, sample_rate=self.config.sample_rate)
        if samples is None:
            return False

        scores = model.predict(samples)
        threshold = 0.5
        return any(score >= threshold for score in scores.values())


class WakeWordDetector:
    """Local wake word detection with optional OpenWakeWord audio backend.

    Transcript keyword matching remains the fallback when openwakeword is not
    installed or when operating on already-transcribed text.
    """

    def __init__(
        self,
        config: VoiceConfig,
        *,
        on_wake: Callable[[], None] | None = None,
        on_session_end: Callable[[], None] | None = None,
        on_audio_cue: Callable[[], None] | None = None,
        audio_backend: OpenWakeWordBackend | None = None,
    ) -> None:
        self.config = config
        self._on_wake = on_wake
        self._on_session_end = on_session_end
        self._on_audio_cue = on_audio_cue
        self._active = False
        self._wake_pattern = self._compile_phrase(config.wake_word)
        self._end_pattern = self._compile_phrase(config.session_end_phrase)
        self._audio_backend = audio_backend or OpenWakeWordBackend(config)

    @property
    def wake_backend(self) -> str:
        if self._audio_backend.available:
            return "openwakeword"
        return "transcript"

    @property
    def active(self) -> bool:
        return self._active

    def activate_passive(self) -> None:
        self._active = False

    def activate_listening(self) -> None:
        self._active = True
        if self.config.audio_cue and self._on_audio_cue:
            self._on_audio_cue()

    def process_audio(self, audio: bytes) -> bool:
        """Return True when wake word detected in raw audio (passive mode only)."""

        if self._active:
            return False
        if not self._audio_backend.detect(audio):
            return False

        self.activate_listening()
        if self._on_wake:
            self._on_wake()
        return True

    def process_transcript(self, text: str) -> str | None:
        """Return cleaned user text, or None if wake/end phrase handled."""

        normalized = text.strip()
        if not normalized:
            return None

        if not self._active:
            if self._wake_pattern.search(normalized):
                self.activate_listening()
                if self._on_wake:
                    self._on_wake()
                remainder = self._wake_pattern.sub("", normalized, count=1).strip(" ,.")
                remainder = re.sub(
                    r"^(hey|ok|okay|hi)\s+",
                    "",
                    remainder,
                    flags=re.IGNORECASE,
                ).strip()
                return remainder or None
            return None

        if self._end_pattern.search(normalized):
            self._active = False
            if self._on_session_end:
                self._on_session_end()
            return None

        return normalized

    @staticmethod
    def _compile_phrase(phrase: str) -> re.Pattern[str]:
        escaped = re.escape(phrase.strip())
        return re.compile(escaped, re.IGNORECASE)
