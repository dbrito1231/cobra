"""Wake word detection and session end phrase handling."""

from __future__ import annotations

import re
from collections.abc import Callable

from voice.config import VoiceConfig


class WakeWordDetector:
    """Local wake word detection using keyword matching.

    Production deployments can swap in OpenWakeWord or Porcupine without
    changing the VoiceService interface.
    """

    def __init__(
        self,
        config: VoiceConfig,
        *,
        on_wake: Callable[[], None] | None = None,
        on_session_end: Callable[[], None] | None = None,
        on_audio_cue: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self._on_wake = on_wake
        self._on_session_end = on_session_end
        self._on_audio_cue = on_audio_cue
        self._active = False
        self._wake_pattern = self._compile_phrase(config.wake_word)
        self._end_pattern = self._compile_phrase(config.session_end_phrase)

    @property
    def active(self) -> bool:
        return self._active

    def activate_passive(self) -> None:
        self._active = False

    def activate_listening(self) -> None:
        self._active = True
        if self.config.audio_cue and self._on_audio_cue:
            self._on_audio_cue()

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
