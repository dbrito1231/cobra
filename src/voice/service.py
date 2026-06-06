"""Voice service — coordinates wake word, input, output, and lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Union

from voice.cloning import VoiceCloningManager
from voice.config import VoiceConfig
from voice.input_pipeline import VoiceInputPipeline
from voice.interruption import InterruptionQueue
from voice.models import HealthStatus, SessionState, TranscribedTextEvent
from voice.output import VoiceOutput
from voice.session import SessionLifecycle
from voice.wake_word import WakeWordDetector

InputHandler = Callable[
    [TranscribedTextEvent], Union[Awaitable[Any], Any]
]


class VoiceService:
    """Top-level Voice Layer initialized in Orchestrator Phase 4."""

    def __init__(
        self,
        config: VoiceConfig | None = None,
        *,
        input_handler: InputHandler | None = None,
        on_text_output: Callable[[str], None] | None = None,
        on_voice_state: Callable[[SessionState], None] | None = None,
        input_allowed: Callable[[], bool] | None = None,
    ) -> None:
        self.config = config or VoiceConfig.from_env()
        self.lifecycle = SessionLifecycle()
        self.interruption = InterruptionQueue()
        self._input_handler = input_handler
        self._on_voice_state = on_voice_state
        self._input_allowed = input_allowed or (lambda: True)
        self._initialized = False
        self._last_spoken: list[str] = []

        self.output = VoiceOutput(
            self.config,
            on_text=self._emit_text_output(on_text_output),
            on_speech=self._record_speech,
        )
        self.cloning = VoiceCloningManager(self.config, self.output)
        self.wake_word = WakeWordDetector(
            self.config,
            on_wake=self._on_wake,
            on_session_end=self._on_session_end,
            on_audio_cue=self._play_audio_cue,
        )
        self.input_pipeline = VoiceInputPipeline(
            self.config,
            on_low_confidence=self._play_audio_cue,
        )

    def initialize(self) -> None:
        self.wake_word.activate_passive()
        self.lifecycle.on_session_end()
        self._emit_state(SessionState.PASSIVE)
        self._initialized = True

    async def shutdown(self) -> None:
        self._initialized = False
        self.wake_word.activate_passive()
        self.lifecycle.on_session_end()

    async def handle_audio(self, audio: bytes) -> TranscribedTextEvent | None:
        if not self._initialized or not self._input_allowed():
            return None

        result = self.input_pipeline.process_audio(audio)
        if result is None:
            return None
        return await self._handle_transcript(result.text, result.confidence, result.mood)

    async def handle_text(self, text: str, *, confidence: float = 1.0) -> TranscribedTextEvent | None:
        """Dev/test path for text-as-speech input."""

        if not self._initialized or not self._input_allowed():
            return None

        if self.interruption.responding:
            cleaned = self.wake_word.process_transcript(text)
            if cleaned is None:
                self.interruption.enqueue(text)
                return None

        cleaned = self.wake_word.process_transcript(text)
        if cleaned is None:
            return None

        result = self.input_pipeline.process_text(cleaned, confidence=confidence)
        if result is None:
            return None
        return await self._handle_transcript(result.text, result.confidence, result.mood)

    async def deliver_response(self, text: str, mood_context: dict | None = None) -> None:
        from voice.models import MoodLevel, MoodResult

        mood = MoodResult()
        if mood_context:
            raw = mood_context.get("mood", MoodLevel.NEUTRAL.value)
            mood = MoodResult(
                mood=MoodLevel(raw),
                energy=float(mood_context.get("energy", 0.5)),
                speaking_rate=float(mood_context.get("speaking_rate", 1.0)),
            )

        self.lifecycle.on_user_speech()
        self.interruption.begin_response()
        self._emit_state(SessionState.RESPONDING)
        await self.output.deliver(text, mood)
        self.interruption.end_response()
        self.lifecycle.on_response_complete()
        self._emit_state(SessionState.ACTIVE)

        queued = self.interruption.pop_next()
        if queued:
            await self.handle_text(queued)

    def health(self) -> HealthStatus:
        if not self._initialized:
            return HealthStatus(healthy=False, message="not initialized")
        status = self.output.model_status()
        if not status.ready:
            return HealthStatus(healthy=True, message=status.message, degraded=True)
        return HealthStatus(healthy=True)

    def last_spoken(self) -> list[str]:
        return list(self._last_spoken)

    async def _handle_transcript(
        self,
        text: str,
        confidence: float,
        mood,
    ) -> TranscribedTextEvent | None:
        self.lifecycle.on_user_speech()
        self._emit_state(SessionState.RESPONDING)
        event = TranscribedTextEvent(text=text, mood=mood)

        if self._input_handler:
            result = self._input_handler(event)
            if asyncio.iscoroutine(result):
                await result

        self.lifecycle.on_response_complete()
        self._emit_state(SessionState.ACTIVE)
        return event

    def _on_wake(self) -> None:
        self.lifecycle.on_wake_word()
        self._emit_state(SessionState.ACTIVE)

    def _on_session_end(self) -> None:
        self.lifecycle.on_session_end()
        self.wake_word.activate_passive()
        self._emit_state(SessionState.PASSIVE)

    def _play_audio_cue(self) -> None:
        pass

    def _emit_text_output(
        self, handler: Callable[[str], None] | None
    ) -> Callable[[str, Any], None] | None:
        if handler is None:
            return None

        def _wrapper(text: str, _mood) -> None:
            handler(text)

        return _wrapper

    def _record_speech(self, text: str, rate: float) -> None:
        self._last_spoken.append(f"{text}@{rate:.2f}")

    def _emit_state(self, state: SessionState) -> None:
        if self._on_voice_state:
            self._on_voice_state(state)
