"""Shared context state per specs/brain/context-awareness.md."""

from __future__ import annotations

from datetime import datetime, timezone

from brain.models import ExecutionPlan, SharedContext
from voice.models import MoodLevel, MoodResult


class ContextBuilder:
    """Builds read-only shared context for each pipeline run."""

    def __init__(self) -> None:
        self._current_task: str | None = None
        self._mood: str = MoodLevel.NEUTRAL.value
        self._energy: float = 0.5

    @property
    def current_task(self) -> str | None:
        return self._current_task

    def declare_task(self, task: str) -> None:
        self._current_task = task.strip() or None

    def update_mood(self, mood: MoodResult | None) -> None:
        if mood is None:
            return
        self._mood = mood.mood.value
        self._energy = mood.energy

    def infer_mood_from_text(self, text: str) -> None:
        words = len(text.split())
        if words <= 6:
            self._mood = MoodLevel.BUSY.value
            self._energy = 0.3
        elif words >= 30:
            self._mood = MoodLevel.RELAXED.value
            self._energy = 0.8
        else:
            self._mood = MoodLevel.NEUTRAL.value
            self._energy = 0.5

    def detect_task_shift(self, text: str) -> None:
        lowered = text.lower()
        if lowered.startswith("let's work on ") or lowered.startswith("task:"):
            task = text.split(":", 1)[-1].strip() if ":" in text else text[14:].strip()
            self.declare_task(task)

    def build(
        self,
        user_text: str,
        *,
        plan: ExecutionPlan | None = None,
        route=None,
    ) -> SharedContext:
        return SharedContext(
            timestamp=datetime.now(timezone.utc),
            current_task=self._current_task,
            mood=self._mood,
            energy=self._energy,
            user_text=user_text,
            execution_plan=plan,
            route=route,
        )

    def reset_session(self) -> None:
        self._current_task = None
        self._mood = MoodLevel.NEUTRAL.value
        self._energy = 0.5
