"""Input mode layer — normalize voice and text per specs/brain/input-mode-layer.md."""

from __future__ import annotations

from dataclasses import dataclass

from voice.models import MoodResult, TranscribedTextEvent


@dataclass
class NormalizedInput:
    text: str
    source: str
    mood: MoodResult | None = None
    needs_confirmation: bool = False
    confirmation_prompt: str = ""


class InputModeLayer:
    """Produces clean text for downstream brain processing."""

    CONFIDENCE_THRESHOLD = 0.5

    def normalize_text(self, text: str, *, mood: MoodResult | None = None) -> NormalizedInput:
        cleaned = " ".join(text.strip().split())
        return NormalizedInput(text=cleaned, source="text", mood=mood)

    def normalize_voice(self, event: TranscribedTextEvent) -> NormalizedInput:
        cleaned = " ".join(event.text.strip().split())
        if event.confidence < self.CONFIDENCE_THRESHOLD:
            return NormalizedInput(
                text=cleaned,
                source="voice",
                mood=event.mood,
                needs_confirmation=True,
                confirmation_prompt=(
                    f"I heard: \"{cleaned}\" — could you repeat or confirm that?"
                ),
            )
        return NormalizedInput(text=cleaned, source="voice", mood=event.mood)
