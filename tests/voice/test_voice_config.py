"""Tests for VoiceConfig model paths."""

from __future__ import annotations

from pathlib import Path

from voice.config import VoiceConfig


def test_model_paths_under_voice_dir(tmp_path: Path) -> None:
    root = tmp_path / "voice"
    config = VoiceConfig(voice_model_path=root, whisper_model="tiny")
    assert config.model_marker_path == root / "model.ready"
    assert config.speaker_wav_path == root / "speaker.wav"
    assert config.xtts_model_dir == root / "xtts"


def test_from_config_dict_reads_model_paths(tmp_path: Path) -> None:
    config = VoiceConfig.from_config_dict(
        {
            "voice": {
                "voice_model_path": str(tmp_path / "custom"),
                "whisper_model": "small",
                "whisper_model_path": str(tmp_path / "whisper-cache"),
                "openwakeword_model": "alexa",
                "sample_rate": 22050,
            }
        }
    )
    assert config.whisper_model == "small"
    assert config.whisper_model_path == tmp_path / "whisper-cache"
    assert config.openwakeword_model == "alexa"
    assert config.sample_rate == 22050
