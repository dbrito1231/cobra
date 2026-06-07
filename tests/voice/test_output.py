"""Tests for TTS output and cloning fallbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from voice.cloning import VoiceCloningManager
from voice.config import VoiceConfig
from voice.output import VoiceOutput
from voice.tts import COQUI_TTS_AVAILABLE, TTSSynthesizer


@pytest.fixture
def voice_config(tmp_path: Path) -> VoiceConfig:
    return VoiceConfig(voice_model_path=tmp_path / "voice")


@pytest.mark.asyncio
class TestVoiceOutput:
    async def test_text_only_when_model_missing(self, voice_config: VoiceConfig) -> None:
        texts: list[str] = []
        output = VoiceOutput(voice_config, on_text=lambda text, _mood: texts.append(text))
        assert output.tts_backend == ("xtts" if COQUI_TTS_AVAILABLE else "text-only")
        await output.deliver("Hello")
        assert texts == ["Hello"]

    async def test_speech_callback_when_model_ready_without_tts(
        self, voice_config: VoiceConfig
    ) -> None:
        spoken: list[str] = []
        output = VoiceOutput(
            voice_config,
            on_speech=lambda text, rate: spoken.append(f"{text}:{rate}"),
        )
        output.mark_model_ready()
        await output.deliver("Ready")
        assert spoken


class TestTTSSynthesizer:
    def test_train_from_samples_writes_speaker_clip(
        self, voice_config: VoiceConfig, tmp_path: Path
    ) -> None:
        sample = tmp_path / "sample.wav"
        sample.write_bytes(b"RIFFfake")
        synthesizer = TTSSynthesizer(voice_config)
        assert synthesizer.train_from_samples([sample]) is True
        assert voice_config.speaker_wav_path.exists()


class TestVoiceCloning:
    def test_stub_training_marks_model_ready(self, voice_config: VoiceConfig) -> None:
        output = VoiceOutput(voice_config)
        manager = VoiceCloningManager(voice_config, output)
        assert manager.train_local_model() is False
        manager.session.sample_seconds = 60.0
        assert manager.train_local_model() is True
        assert output.model_status().ready

    def test_xtts_path_uses_synthesizer(self, voice_config: VoiceConfig, tmp_path: Path) -> None:
        sample = tmp_path / "sample.wav"
        sample.write_bytes(b"RIFFfake")
        synthesizer = MagicMock()
        synthesizer.available = True
        synthesizer.train_from_samples.return_value = True
        output = VoiceOutput(voice_config, synthesizer=synthesizer)
        manager = VoiceCloningManager(voice_config, output, synthesizer=synthesizer)
        manager.session.samples = [sample]
        manager.session.sample_seconds = 60.0
        assert manager.train_local_model() is True
        synthesizer.train_from_samples.assert_called_once()
