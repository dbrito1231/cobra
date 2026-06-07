"""First-run onboarding state per specs/onboarding/first-run-sequence.md."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from brain.service import BrainService
    from voice.service import VoiceService


class OnboardingPhase(str, Enum):
    CONFIG = "config"
    VOICE = "voice"
    SEED = "seed"
    COMPLETE = "complete"


@dataclass
class OnboardingStateData:
    phase: str = OnboardingPhase.VOICE.value
    voice_enrollment_complete: bool = False
    personality_enrollment_complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OnboardingStateData:
        return cls(
            phase=str(data.get("phase", OnboardingPhase.VOICE.value)),
            voice_enrollment_complete=bool(data.get("voice_enrollment_complete")),
            personality_enrollment_complete=bool(data.get("personality_enrollment_complete")),
        )


class OnboardingManager:
    """Tracks first-run voice → seed → operational progression."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self._data = self._load()

    def _load(self) -> OnboardingStateData:
        if not self.state_path.exists():
            return OnboardingStateData()
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return OnboardingStateData()
        return OnboardingStateData.from_dict(raw)

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self._data.to_dict(), indent=2),
            encoding="utf-8",
        )

    @property
    def data(self) -> OnboardingStateData:
        return self._data

    def current_phase(self) -> OnboardingPhase:
        try:
            return OnboardingPhase(self._data.phase)
        except ValueError:
            return OnboardingPhase.VOICE

    def is_operational(self) -> bool:
        return self._data.phase == OnboardingPhase.COMPLETE.value

    def sync(
        self,
        *,
        voice: VoiceService,
        brain: BrainService,
        needs_wizard: bool,
    ) -> None:
        if needs_wizard:
            self._data.phase = OnboardingPhase.CONFIG.value
            self._data.voice_enrollment_complete = False
            self._data.personality_enrollment_complete = False
            self._save()
            return

        voice_done = voice.enrollment_complete()
        personality_done = brain.seed.profile_complete()

        self._data.voice_enrollment_complete = voice_done
        self._data.personality_enrollment_complete = personality_done

        if voice_done and personality_done:
            self._data.phase = OnboardingPhase.COMPLETE.value
        elif voice_done:
            self._data.phase = OnboardingPhase.SEED.value
        else:
            self._data.phase = OnboardingPhase.VOICE.value
        self._save()

    def mark_voice_complete(self) -> None:
        self._data.voice_enrollment_complete = True
        if self._data.personality_enrollment_complete:
            self._data.phase = OnboardingPhase.COMPLETE.value
        else:
            self._data.phase = OnboardingPhase.SEED.value
        self._save()

    def mark_personality_complete(self) -> None:
        self._data.personality_enrollment_complete = True
        if self._data.voice_enrollment_complete:
            self._data.phase = OnboardingPhase.COMPLETE.value
        self._save()

    def to_payload(self, *, blocked_reason: str = "") -> dict[str, Any]:
        return {
            "phase": self._data.phase,
            "voice_complete": self._data.voice_enrollment_complete,
            "personality_complete": self._data.personality_enrollment_complete,
            "operational": self.is_operational(),
            "blocked_reason": blocked_reason,
        }
