"""Voice layer data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    """Voice session lifecycle states LC1–LC3."""

    PASSIVE = "passive"
    ACTIVE = "active"
    RESPONDING = "responding"


class MoodLevel(str, Enum):
    """Inferred mood/energy for TTS speed adaptation."""

    BUSY = "busy"
    NEUTRAL = "neutral"
    RELAXED = "relaxed"


@dataclass
class MoodResult:
    """Mood inference output M1–M4."""

    mood: MoodLevel = MoodLevel.NEUTRAL
    energy: float = 0.5
    speaking_rate: float = 1.0

    def to_context(self) -> dict[str, Any]:
        return {
            "mood": self.mood.value,
            "energy": self.energy,
            "speaking_rate": self.speaking_rate,
        }


@dataclass
class TranscriptionResult:
    """Whisper transcription with confidence I1–I5."""

    text: str
    confidence: float
    mood: MoodResult = field(default_factory=MoodResult)

    @property
    def acceptable(self) -> bool:
        return bool(self.text.strip()) and self.confidence >= 0.5


@dataclass
class TranscribedTextEvent:
    """Event published to brain input mode layer."""

    text: str
    mood: MoodResult
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "mood": self.mood.to_context(),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VoiceModelStatus:
    """Cloned voice model readiness."""

    ready: bool
    path: str
    message: str = "ok"


@dataclass
class HealthStatus:
    healthy: bool
    message: str = "ok"
    degraded: bool = False
