"""XTTS / Coqui TTS integration with text-only fallback."""

from __future__ import annotations

from pathlib import Path

from voice.config import VoiceConfig

try:
    from TTS.api import TTS as CoquiTTS

    COQUI_TTS_AVAILABLE = True
except ImportError:
    COQUI_TTS_AVAILABLE = False
    CoquiTTS = None  # type: ignore[misc, assignment]


class TTSSynthesizer:
    """Local XTTS synthesis when Coqui TTS is installed."""

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._engine: CoquiTTS | None = None

    @property
    def available(self) -> bool:
        return COQUI_TTS_AVAILABLE

    @property
    def backend(self) -> str:
        return "xtts" if COQUI_TTS_AVAILABLE else "text-only"

    def _ensure_engine(self) -> CoquiTTS | None:
        if not COQUI_TTS_AVAILABLE:
            return None
        if self._engine is None:
            model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
            self._engine = CoquiTTS(model_name=model_name)
        return self._engine

    def synthesize(self, text: str, *, rate: float = 1.0) -> bytes | None:
        engine = self._ensure_engine()
        if engine is None or not text.strip():
            return None

        speaker_wav = self.config.speaker_wav_path
        if not speaker_wav.exists():
            return None

        output_path = self.config.voice_model_path / "_tts_output.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        engine.tts_to_file(
            text=text,
            file_path=str(output_path),
            speaker_wav=str(speaker_wav),
            language="en",
            speed=rate,
        )
        data = output_path.read_bytes()
        output_path.unlink(missing_ok=True)
        return data

    def train_from_samples(self, sample_paths: list[Path]) -> bool:
        """Prepare speaker reference clip for XTTS from recorded samples."""

        if not sample_paths:
            return False

        self.config.voice_model_path.mkdir(parents=True, exist_ok=True)
        speaker_wav = self.config.speaker_wav_path
        speaker_wav.write_bytes(Path(sample_paths[0]).read_bytes())

        if COQUI_TTS_AVAILABLE:
            self.config.xtts_model_dir.mkdir(parents=True, exist_ok=True)
            marker = self.config.xtts_model_dir / "trained.txt"
            marker.write_text(
                f"speaker={speaker_wav.name}\nsamples={len(sample_paths)}\n",
                encoding="utf-8",
            )
        return True
