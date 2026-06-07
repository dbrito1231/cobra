"""Shared audio helpers for voice production backends."""

from __future__ import annotations

import io
import math
import struct
import wave
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy ships with faster-whisper
    NUMPY_AVAILABLE = False
    np = None  # type: ignore[assignment]


def pcm16_bytes_to_float32(
    audio: bytes, *, sample_rate: int = 16000
) -> "npt.NDArray[np.floating]" | None:
    """Convert raw PCM16 mono bytes to normalized float32 samples."""

    if not NUMPY_AVAILABLE or not audio:
        return None
    count = len(audio) // 2
    if count == 0:
        return None
    samples = struct.unpack(f"<{count}h", audio[: count * 2])
    return np.array(samples, dtype=np.float32) / 32768.0


def bytes_to_float32(audio: bytes, *, sample_rate: int = 16000) -> "npt.NDArray[np.floating]" | None:
    """Decode WAV or raw PCM16 bytes into float32 mono samples."""

    if not audio:
        return None
    if audio[:4] == b"RIFF":
        return wav_bytes_to_float32(audio)
    return pcm16_bytes_to_float32(audio, sample_rate=sample_rate)


def wav_bytes_to_float32(data: bytes) -> "npt.NDArray[np.floating]" | None:
    if not NUMPY_AVAILABLE:
        return None
    with wave.open(io.BytesIO(data), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        sample_width = wf.getsampwidth()
        if sample_width == 2:
            count = len(frames) // 2
            samples = struct.unpack(f"<{count}h", frames)
            return np.array(samples, dtype=np.float32) / 32768.0
        if sample_width == 1:
            samples = struct.unpack(f"{len(frames)}B", frames)
            return (np.array(samples, dtype=np.float32) - 128.0) / 128.0
    return None


def generate_beep_wav(
    *,
    frequency: float = 880.0,
    duration_seconds: float = 0.15,
    sample_rate: int = 16000,
    volume: float = 0.3,
) -> bytes:
    """Generate a short sine-wave beep as in-memory WAV bytes."""

    frame_count = int(sample_rate * duration_seconds)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(frame_count):
            t = i / sample_rate
            sample = int(volume * 32767.0 * math.sin(2.0 * math.pi * frequency * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(bytes(frames))
    return buffer.getvalue()
