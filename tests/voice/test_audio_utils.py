"""Tests for audio utility helpers."""

from __future__ import annotations

import pytest

from voice.audio_utils import NUMPY_AVAILABLE, generate_beep_wav, pcm16_bytes_to_float32


def test_generate_beep_wav_is_valid_header() -> None:
    wav = generate_beep_wav(duration_seconds=0.05)
    assert wav[:4] == b"RIFF"
    assert b"WAVE" in wav


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
def test_pcm16_bytes_to_float32_normalizes() -> None:
    samples = pcm16_bytes_to_float32(b"\x00\x00\xff\x7f")
    assert samples is not None
    assert samples[0] == 0.0
    assert samples[1] == pytest.approx(32767 / 32768.0)
