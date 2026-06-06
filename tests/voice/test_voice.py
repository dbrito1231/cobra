"""Tests for the Voice component."""

from __future__ import annotations

from pathlib import Path

import pytest

from voice.cloning import VoiceCloningManager
from voice.config import VoiceConfig
from voice.interruption import InterruptionQueue
from voice.models import MoodLevel, SessionState
from voice.mood import MoodInferencer
from voice.output import VoiceOutput
from voice.service import VoiceService
from voice.session import SessionLifecycle
from voice.wake_word import WakeWordDetector


@pytest.fixture
def voice_config(tmp_path: Path) -> VoiceConfig:
    return VoiceConfig(
        wake_word="cobra",
        session_end_phrase="That's all for now C.O.B.R.A.",
        voice_model_path=tmp_path / "voice",
        confidence_threshold=0.5,
    )


class TestWakeWordDetector:
    def test_wake_word_activates_session(self, voice_config: VoiceConfig) -> None:
        activated = {"value": False}

        def on_wake() -> None:
            activated["value"] = True

        detector = WakeWordDetector(voice_config, on_wake=on_wake)
        result = detector.process_transcript("Hey cobra what time is it")
        assert result == "what time is it"
        assert detector.active
        assert activated["value"]

    def test_session_end_returns_to_passive(self, voice_config: VoiceConfig) -> None:
        ended = {"value": False}

        def on_end() -> None:
            ended["value"] = True

        detector = WakeWordDetector(voice_config, on_session_end=on_end)
        detector.activate_listening()
        result = detector.process_transcript("That's all for now C.O.B.R.A.")
        assert result is None
        assert ended["value"]
        assert not detector.active


class TestSessionLifecycle:
    def test_state_transitions(self) -> None:
        lifecycle = SessionLifecycle()
        assert lifecycle.state == SessionState.PASSIVE
        lifecycle.on_wake_word()
        assert lifecycle.state == SessionState.ACTIVE
        lifecycle.on_user_speech()
        assert lifecycle.state == SessionState.RESPONDING
        lifecycle.on_response_complete()
        assert lifecycle.state == SessionState.ACTIVE
        lifecycle.on_session_end()
        assert lifecycle.state == SessionState.PASSIVE


class TestInterruptionQueue:
    def test_queues_during_response(self) -> None:
        queue = InterruptionQueue()
        queue.begin_response()
        queue.enqueue("follow up question")
        assert queue.responding
        next_input = queue.end_response()
        assert next_input == "follow up question"


class TestMoodInferencer:
    def test_busy_mood(self) -> None:
        mood = MoodInferencer().infer(
            duration_seconds=0.5,
            peak_amplitude=0.9,
            pause_ratio=0.1,
        )
        assert mood.mood == MoodLevel.BUSY
        assert mood.speaking_rate > 1.0


class TestVoiceService:
    @pytest.mark.asyncio
    async def test_handle_text_after_wake_word(self, voice_config: VoiceConfig) -> None:
        events: list = []
        service = VoiceService(
            voice_config,
            input_handler=lambda event: events.append(event),
        )
        service.initialize()
        assert await service.handle_text("cobra hello there") is not None
        assert events
        assert events[0].text == "hello there"

    @pytest.mark.asyncio
    async def test_deliver_response_records_speech(self, voice_config: VoiceConfig) -> None:
        spoken: list[str] = []
        service = VoiceService(
            voice_config,
            on_text_output=lambda text: None,
        )
        service.output = VoiceOutput(
            voice_config,
            on_speech=lambda text, rate: spoken.append(text),
        )
        service.output.mark_model_ready()
        service.initialize()
        await service.deliver_response("Hello from C.O.B.R.A.")
        assert spoken


class TestVoiceCloning:
    def test_training_requires_minimum_samples(self, voice_config: VoiceConfig) -> None:
        output = VoiceOutput(voice_config)
        manager = VoiceCloningManager(voice_config, output)
        assert manager.train_local_model() is False
        manager.session.sample_seconds = 60.0
        assert manager.train_local_model() is True
        assert output.model_status().ready
