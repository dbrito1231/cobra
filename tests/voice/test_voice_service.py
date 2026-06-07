"""Tests for VoiceService audio cues and mic capture stub."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from voice.config import VoiceConfig
from voice.service import SOUNDDEVICE_AVAILABLE, VoiceService


@pytest.fixture
def voice_config(tmp_path: Path) -> VoiceConfig:
    return VoiceConfig(voice_model_path=tmp_path / "voice")


class TestAudioCue:
    def test_play_audio_cue_generates_wav(self, voice_config: VoiceConfig) -> None:
        service = VoiceService(voice_config)
        service._play_audio_cue()
        cue = service.last_audio_cue()
        assert cue is not None
        assert cue[:4] == b"RIFF"

    def test_custom_cue_path(self, voice_config: VoiceConfig, tmp_path: Path) -> None:
        cue_file = tmp_path / "custom.wav"
        cue_file.write_bytes(b"CUSTOM-CUE")
        config = VoiceConfig(
            voice_model_path=voice_config.voice_model_path,
            audio_cue_path=cue_file,
        )
        service = VoiceService(config)
        service._play_audio_cue()
        assert service.last_audio_cue() == b"CUSTOM-CUE"


class TestMicCaptureStub:
    def test_start_mic_loop_without_sounddevice(self, voice_config: VoiceConfig) -> None:
        service = VoiceService(voice_config)
        with patch("voice.service.SOUNDDEVICE_AVAILABLE", False):
            assert service.start_mic_loop(lambda _chunk: None) is False

    def test_start_mic_loop_with_sounddevice(self, voice_config: VoiceConfig) -> None:
        service = VoiceService(voice_config)
        stop_after = {"count": 0}

        def on_chunk(_chunk: bytes) -> None:
            stop_after["count"] += 1
            if stop_after["count"] >= 1:
                service._mic_stop.set()

        with patch("voice.service.SOUNDDEVICE_AVAILABLE", True):
            with patch("voice.service.sd") as mock_sd:
                mock_sd.rec.return_value = b"\x00\x00"
                assert service.start_mic_loop(on_chunk) is True
                service._mic_thread.join(timeout=2.0)
                service._mic_thread = None

    def test_mic_capture_available_flag(self, voice_config: VoiceConfig) -> None:
        service = VoiceService(voice_config)
        assert service.mic_capture_available == SOUNDDEVICE_AVAILABLE
