"""Tests for wake word audio backend and transcript fallback."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from voice.config import VoiceConfig
from voice.wake_word import OpenWakeWordBackend, WakeWordDetector


@pytest.fixture
def voice_config() -> VoiceConfig:
    return VoiceConfig(wake_word="cobra")


class TestOpenWakeWordBackend:
    def test_detect_false_when_backend_unavailable(self, voice_config: VoiceConfig) -> None:
        backend = OpenWakeWordBackend(voice_config)
        assert backend.detect(b"\x00\x01") is False

    def test_detect_true_when_model_scores_high(
        self, voice_config: VoiceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = OpenWakeWordBackend(voice_config)
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_jarvis": 0.9}
        monkeypatch.setattr(
            "voice.wake_word.bytes_to_float32", lambda *_a, **_k: [0.0, 0.1]
        )
        monkeypatch.setattr(backend, "_ensure_model", lambda: mock_model)
        assert backend.detect(b"\x00\x01") is True


class TestWakeWordDetectorAudio:
    def test_process_audio_triggers_wake(self, voice_config: VoiceConfig) -> None:
        activated = {"value": False}
        backend = MagicMock()
        backend.detect.return_value = True
        backend.available = True

        detector = WakeWordDetector(
            voice_config,
            on_wake=lambda: activated.update(value=True),
            audio_backend=backend,
        )
        assert detector.process_audio(b"chunk") is True
        assert detector.active
        assert activated["value"]

    def test_transcript_fallback_still_works(self, voice_config: VoiceConfig) -> None:
        detector = WakeWordDetector(voice_config)
        assert detector.wake_backend == "transcript"
        result = detector.process_transcript("Hey cobra status report")
        assert result == "status report"
