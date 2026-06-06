"""Mood inference from speech patterns M1–M4."""

from __future__ import annotations

from voice.models import MoodLevel, MoodResult


class MoodInferencer:
    """Infer mood/energy from lightweight audio feature proxies."""

    def infer(
        self,
        *,
        duration_seconds: float,
        peak_amplitude: float,
        pause_ratio: float,
    ) -> MoodResult:
        if duration_seconds <= 0:
            return MoodResult()

        words_per_second = max(0.1, 1.0 / max(duration_seconds, 0.1))
        if words_per_second > 2.5 or peak_amplitude > 0.85:
            mood = MoodLevel.BUSY
            rate = 1.2
            energy = 0.8
        elif pause_ratio > 0.35 or words_per_second < 1.2:
            mood = MoodLevel.RELAXED
            rate = 0.85
            energy = 0.35
        else:
            mood = MoodLevel.NEUTRAL
            rate = 1.0
            energy = 0.5

        return MoodResult(mood=mood, energy=energy, speaking_rate=rate)

    def infer_from_text_proxy(
        self,
        text: str,
        *,
        confidence: float,
    ) -> MoodResult:
        """Fallback when raw audio features are unavailable (tests/dev)."""

        length_factor = min(len(text.split()) / 20.0, 1.0)
        pause_ratio = 0.2 if "..." in text else 0.1
        return self.infer(
            duration_seconds=max(1.0, len(text.split()) / 2.0),
            peak_amplitude=min(1.0, confidence + length_factor * 0.2),
            pause_ratio=pause_ratio,
        )
