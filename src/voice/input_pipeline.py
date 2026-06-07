"""Voice input pipeline I1–I5."""

from __future__ import annotations

import math
from collections.abc import Callable

from voice.audio_utils import bytes_to_float32
from voice.config import VoiceConfig
from voice.models import TranscriptionResult
from voice.mood import MoodInferencer

try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None  # type: ignore[misc, assignment]


def logprob_to_confidence(avg_logprob: float) -> float:
    """Map Whisper segment avg_logprob to a 0–1 confidence score."""

    # avg_logprob is typically in [-1, 0]; exp maps toward (0, 1].
    return max(0.0, min(1.0, math.exp(avg_logprob)))


class WhisperTranscriber:
    """Local faster-whisper backend with UTF-8 stub fallback."""

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._model: WhisperModel | None = None

    @property
    def backend(self) -> str:
        return "faster-whisper" if FASTER_WHISPER_AVAILABLE else "utf8-stub"

    def _ensure_model(self) -> WhisperModel | None:
        if not FASTER_WHISPER_AVAILABLE:
            return None
        if self._model is None:
            model_path = (
                str(self.config.whisper_model_path)
                if self.config.whisper_model_path
                else self.config.whisper_model
            )
            self._model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
            )
        return self._model

    def transcribe(self, audio: bytes) -> tuple[str, float]:
        if not audio:
            return "", 0.0

        model = self._ensure_model()
        if model is None:
            return self._stub_transcribe(audio)

        samples = bytes_to_float32(audio, sample_rate=self.config.sample_rate)
        if samples is None:
            return "", 0.0

        segments, _info = model.transcribe(
            samples,
            language="en",
            vad_filter=True,
        )
        text_parts: list[str] = []
        logprobs: list[float] = []
        for segment in segments:
            text_parts.append(segment.text.strip())
            if segment.avg_logprob is not None:
                logprobs.append(segment.avg_logprob)

        text = " ".join(part for part in text_parts if part).strip()
        if not logprobs:
            confidence = 0.9 if text else 0.0
        else:
            confidence = logprob_to_confidence(sum(logprobs) / len(logprobs))
        return text, confidence

    @staticmethod
    def _stub_transcribe(audio: bytes) -> tuple[str, float]:
        """Dev/test path: UTF-8 encoded text pretends to be audio."""

        try:
            decoded = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            return "", 0.0
        return decoded, 0.9 if decoded else 0.0


class VoiceInputPipeline:
    """Capture → transcribe → confidence check → handoff to brain."""

    def __init__(
        self,
        config: VoiceConfig,
        *,
        transcribe: Callable[[bytes], tuple[str, float]] | None = None,
        on_low_confidence: Callable[[], None] | None = None,
        transcriber: WhisperTranscriber | None = None,
    ) -> None:
        self.config = config
        self._transcriber = transcriber or WhisperTranscriber(config)
        self._transcribe = transcribe or self._transcriber.transcribe
        self._on_low_confidence = on_low_confidence
        self.mood = MoodInferencer()

    @property
    def transcription_backend(self) -> str:
        if self._transcribe is self._transcriber.transcribe:
            return self._transcriber.backend
        return "custom"

    def process_audio(self, audio: bytes) -> TranscriptionResult | None:
        text, confidence = self._transcribe(audio)
        mood = self.mood.infer_from_text_proxy(text, confidence=confidence)
        result = TranscriptionResult(text=text, confidence=confidence, mood=mood)
        if not self._is_acceptable(result):
            if self.config.audio_cue and self._on_low_confidence:
                self._on_low_confidence()
            return None
        return result

    def process_text(self, text: str, *, confidence: float = 1.0) -> TranscriptionResult | None:
        """Dev/test path when microphone audio is unavailable."""

        mood = self.mood.infer_from_text_proxy(text, confidence=confidence)
        result = TranscriptionResult(text=text, confidence=confidence, mood=mood)
        if not self._is_acceptable(result):
            if self.config.audio_cue and self._on_low_confidence:
                self._on_low_confidence()
            return None
        return result

    def _is_acceptable(self, result: TranscriptionResult) -> bool:
        return bool(result.text.strip()) and result.confidence >= self.config.confidence_threshold
