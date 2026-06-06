"""Voice cloning setup flow CL1–CL7."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from voice.config import VoiceConfig
from voice.output import VoiceOutput

GUIDED_PROMPTS = [
    "The quick brown fox jumps over the lazy dog.",
    "C.O.B.R.A. listens locally and responds with my cloned voice.",
    "Please speak clearly at a natural pace for about one minute.",
    "When I am busy, I prefer concise answers delivered quickly.",
    "When I am relaxed, I enjoy slower and more thoughtful responses.",
]


@dataclass
class CloningSession:
    """Tracks guided recording progress."""

    prompts_completed: int = 0
    sample_seconds: float = 0.0
    approved: bool = False
    samples: list[Path] = field(default_factory=list)

    @property
    def ready_for_training(self) -> bool:
        return self.sample_seconds >= 60.0


class VoiceCloningManager:
    """Guided local voice cloning workflow."""

    def __init__(self, config: VoiceConfig, output: VoiceOutput) -> None:
        self.config = config
        self.output = output
        self.session = CloningSession()
        self.samples_dir = config.voice_model_path / "samples"

    def next_prompt(self) -> str | None:
        if self.session.prompts_completed >= len(GUIDED_PROMPTS):
            return None
        return GUIDED_PROMPTS[self.session.prompts_completed]

    def record_sample(self, audio_path: Path, duration_seconds: float) -> None:
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        target = self.samples_dir / f"sample_{len(self.session.samples):04d}.wav"
        target.write_bytes(Path(audio_path).read_bytes())
        self.session.samples.append(target)
        self.session.sample_seconds += duration_seconds
        self.session.prompts_completed += 1

    def train_local_model(self) -> bool:
        if not self.session.ready_for_training:
            return False
        self.config.voice_model_path.mkdir(parents=True, exist_ok=True)
        model_file = self.config.voice_model_path / "model.bin"
        model_file.write_bytes(b"local-xtts-stub")
        self.output.mark_model_ready()
        return True

    def approve_clone(self) -> None:
        self.session.approved = True

    def reject_clone(self) -> None:
        self.session.approved = False
        self.session.prompts_completed = 0

    def retrain(self) -> None:
        self.output.remove_model()
        self.session = CloningSession()
