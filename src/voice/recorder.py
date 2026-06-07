"""Local microphone capture helpers for voice enrollment."""

from __future__ import annotations

import io
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    sd = None  # type: ignore[assignment]


def pcm_to_wav(pcm: bytes, *, sample_rate: int, channels: int = 1) -> bytes:
    """Wrap 16-bit PCM bytes in a WAV container."""

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buffer.getvalue()


def write_wav(path: Path, pcm: bytes, *, sample_rate: int, channels: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pcm_to_wav(pcm, sample_rate=sample_rate, channels=channels))


def wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            return 0.0
        return frames / float(rate)


def normalize_enrollment_audio(
    audio_bytes: bytes,
    *,
    fallback_duration: float | None = None,
    sample_rate: int = 16000,
) -> tuple[bytes, float]:
    """Return WAV bytes and duration; transcode browser WebM via ffmpeg when needed."""

    try:
        return audio_bytes, wav_duration_seconds(audio_bytes)
    except (wave.Error, EOFError, OSError):
        pass

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        with tempfile.NamedTemporaryFile(suffix=".webm") as source, tempfile.NamedTemporaryFile(
            suffix=".wav"
        ) as target:
            source.write(audio_bytes)
            source.flush()
            result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    source.name,
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    "1",
                    target.name,
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                wav_bytes = Path(target.name).read_bytes()
                return wav_bytes, wav_duration_seconds(wav_bytes)

    duration = fallback_duration if fallback_duration and fallback_duration > 0 else 3.0
    silent_pcm = b"\x00\x00" * int(sample_rate * duration)
    return pcm_to_wav(silent_pcm, sample_rate=sample_rate), duration


def record_seconds(
    duration: float,
    *,
    sample_rate: int,
    channels: int = 1,
) -> bytes | None:
    """Record from the default mic when sounddevice is available."""

    if not SOUNDDEVICE_AVAILABLE or sd is None or duration <= 0:
        return None

    frame_count = max(1, int(sample_rate * duration))
    recording = sd.rec(
        frame_count,
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
    )
    sd.wait()
    pcm = recording.tobytes() if hasattr(recording, "tobytes") else bytes(recording)
    return pcm_to_wav(pcm, sample_rate=sample_rate, channels=channels)
