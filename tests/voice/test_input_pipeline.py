"""Tests for Whisper transcription backends."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from voice.config import VoiceConfig
from voice.input_pipeline import (
    FASTER_WHISPER_AVAILABLE,
    VoiceInputPipeline,
    WhisperTranscriber,
    logprob_to_confidence,
)


@pytest.fixture
def voice_config() -> VoiceConfig:
    return VoiceConfig(confidence_threshold=0.5)


class TestLogprobToConfidence:
    def test_maps_negative_logprob(self) -> None:
        assert logprob_to_confidence(-0.5) == pytest.approx(0.606, rel=0.01)
        assert logprob_to_confidence(0.0) == 1.0


class TestWhisperTranscriberStub:
    def test_utf8_stub_when_whisper_unavailable(self, voice_config: VoiceConfig) -> None:
        transcriber = WhisperTranscriber(voice_config)
        assert transcriber.backend == ("faster-whisper" if FASTER_WHISPER_AVAILABLE else "utf8-stub")
        text, confidence = transcriber.transcribe(b"hello from stub")
        assert text == "hello from stub"
        assert confidence == pytest.approx(0.9)

    def test_empty_audio_returns_zero_confidence(self, voice_config: VoiceConfig) -> None:
        text, confidence = WhisperTranscriber(voice_config).transcribe(b"")
        assert text == ""
        assert confidence == 0.0


class TestWhisperTranscriberMocked:
    def test_uses_segment_logprobs_for_confidence(self, voice_config: VoiceConfig) -> None:
        segment = MagicMock()
        segment.text = " hello"
        segment.avg_logprob = -0.2
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([segment], None)

        transcriber = WhisperTranscriber(voice_config)
        with patch.object(transcriber, "_ensure_model", return_value=mock_model):
            with patch("voice.input_pipeline.bytes_to_float32", return_value=[0.0, 0.1]):
                text, confidence = transcriber.transcribe(b"\x00\x01")

        assert text == "hello"
        assert confidence == pytest.approx(logprob_to_confidence(-0.2))


class TestVoiceInputPipeline:
    def test_rejects_low_confidence(self, voice_config: VoiceConfig) -> None:
        pipeline = VoiceInputPipeline(
            voice_config,
            transcribe=lambda _audio: ("maybe", 0.2),
        )
        assert pipeline.process_audio(b"ignored") is None

    def test_accepts_above_threshold(self, voice_config: VoiceConfig) -> None:
        pipeline = VoiceInputPipeline(
            voice_config,
            transcribe=lambda _audio: ("clear speech", 0.8),
        )
        result = pipeline.process_audio(b"ignored")
        assert result is not None
        assert result.text == "clear speech"
