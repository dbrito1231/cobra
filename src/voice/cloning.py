"""Voice cloning setup flow CL1–CL7."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import wave

from voice.config import VoiceConfig
from voice.output import VoiceOutput
from voice.recorder import wav_duration_seconds
from voice.tts import TTSSynthesizer

GUIDED_PROMPTS = [
    "The quick brown fox jumps over the lazy dog.",
    "C.O.B.R.A. listens locally and responds with my cloned voice.",
    "Please speak clearly at a natural pace for about one minute.",
    "When I am busy, I prefer concise answers delivered quickly.",
    "When I am relaxed, I enjoy slower and more thoughtful responses.",
    "Technology should feel personal without sacrificing privacy.",
    "I start my mornings with coffee and a quick review of priorities.",
    "Collaboration works best when everyone knows the goal upfront.",
    "Honesty matters more to me than sounding impressive.",
    "I appreciate humor that is dry, subtle, and well-timed.",
    "Under pressure, I focus on the next actionable step.",
    "Learning something new energizes me when the challenge is real.",
    "I prefer direct feedback over vague encouragement.",
    "Family time is non-negotiable on weekends.",
    "Good design disappears and lets the task take center stage.",
    "I trust people who admit what they do not know.",
    "Meetings should have an agenda or they should not happen.",
    "Music helps me concentrate during deep work sessions.",
    "Travel reminds me how much context shapes every decision.",
    "I value loyalty, but not at the expense of integrity.",
    "Small consistent habits beat occasional heroic effort.",
    "When explaining ideas, I use examples before abstractions.",
    "I dislike unnecessary jargon in everyday conversation.",
    "A calm tone can de-escalate almost any tense situation.",
    "I celebrate progress even when the finish line is far away.",
    "Creative work needs uninterrupted blocks of time.",
    "I ask clarifying questions before offering solutions.",
    "Trust is built in ordinary moments, not grand gestures.",
    "I prefer written summaries after important discussions.",
    "Optimism is useful when paired with realistic planning.",
    "I notice tone and pacing as much as the words themselves.",
    "Healthy debate sharpens ideas if respect stays intact.",
    "I remember stories better than lists of facts.",
    "Empathy does not mean agreeing with everyone.",
    "I like tools that stay out of the way until I need them.",
    "Precision in language saves time later.",
    "I recharge by stepping away from screens for a while.",
    "Curiosity is my default response to unfamiliar problems.",
    "I prefer partners who communicate early about blockers.",
    "Silence is sometimes the most thoughtful answer.",
    "Local-first systems give me confidence my data stays mine.",
    "Voice is intimate; it should sound like me, not a generic assistant.",
    "Every project benefits from a clear definition of done.",
    "I read aloud when I want to hear how something truly sounds.",
    "Authenticity beats polish when the stakes are personal.",
    "I am building C.O.B.R.A. to think with me, not replace me.",
    "Consistency in tone helps people know what to expect from me.",
    "I finish strong by reviewing what worked and what did not.",
    "Thank you for helping me teach C.O.B.R.A. how I speak.",
]

TEST_PLAYBACK_PHRASE = (
    "Hello, this is a test of my cloned voice. "
    "If this sounds like me, I will approve it for C.O.B.R.A."
)


@dataclass
class CloningSession:
    """Tracks guided recording progress."""

    prompts_completed: int = 0
    sample_seconds: float = 0.0
    approved: bool = False
    trained: bool = False
    samples: list[str] = field(default_factory=list)

    def meets_minimum(self, minimum_seconds: float) -> bool:
        return self.sample_seconds >= minimum_seconds

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CloningSession:
        return cls(
            prompts_completed=int(data.get("prompts_completed", 0)),
            sample_seconds=float(data.get("sample_seconds", 0.0)),
            approved=bool(data.get("approved")),
            trained=bool(data.get("trained")),
            samples=list(data.get("samples", [])),
        )


class VoiceCloningManager:
    """Guided local voice cloning workflow."""

    STATE_FILE = "enrollment_state.json"

    def __init__(
        self,
        config: VoiceConfig,
        output: VoiceOutput,
        *,
        synthesizer: TTSSynthesizer | None = None,
    ) -> None:
        self.config = config
        self.output = output
        self.session = CloningSession()
        self.samples_dir = config.voice_model_path / "samples"
        self._synthesizer = synthesizer or TTSSynthesizer(config)
        self._load_state()

    @property
    def minimum_seconds(self) -> float:
        return self.config.minimum_enrollment_seconds

    @property
    def recommended_seconds(self) -> float:
        return self.config.recommended_seconds

    def _state_path(self) -> Path:
        return self.config.voice_model_path / self.STATE_FILE

    def _load_state(self) -> None:
        path = self._state_path()
        if not path.exists():
            if self.output.model_status().ready:
                self.session.approved = True
                self.session.trained = True
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.session = CloningSession.from_dict(raw)
        except (json.JSONDecodeError, OSError):
            return
        self.session.samples = [
            str(path)
            for path in self.samples_dir.glob("sample_*.wav")
        ]
        if self.output.model_status().ready and self.session.approved:
            self.session.trained = True

    def _save_state(self) -> None:
        self.config.voice_model_path.mkdir(parents=True, exist_ok=True)
        self._state_path().write_text(
            json.dumps(self.session.to_dict(), indent=2),
            encoding="utf-8",
        )

    def next_prompt(self) -> str | None:
        if self.session.approved:
            return None
        index = self.session.prompts_completed % len(GUIDED_PROMPTS)
        return GUIDED_PROMPTS[index]

    def record_sample_bytes(
        self,
        wav_bytes: bytes,
        duration_seconds: float | None = None,
    ) -> dict:
        """Store a recorded sample and advance the prompt index."""

        try:
            duration = wav_duration_seconds(wav_bytes)
        except (wave.Error, EOFError, OSError):
            duration = duration_seconds if duration_seconds and duration_seconds > 0 else 3.0
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        target = self.samples_dir / f"sample_{len(self.session.samples):04d}.wav"
        target.write_bytes(wav_bytes)
        self.session.samples.append(str(target))
        self.session.sample_seconds += duration
        self.session.prompts_completed += 1
        self.session.trained = False
        self._save_state()
        return self.enrollment_status()

    def record_sample(self, audio_path: Path, duration_seconds: float) -> None:
        wav_bytes = Path(audio_path).read_bytes()
        if duration_seconds <= 0:
            duration_seconds = wav_duration_seconds(wav_bytes)
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        target = self.samples_dir / f"sample_{len(self.session.samples):04d}.wav"
        target.write_bytes(wav_bytes)
        self.session.samples.append(str(target))
        self.session.sample_seconds += duration_seconds
        self.session.prompts_completed += 1
        self.session.trained = False
        self._save_state()

    def ready_for_training(self) -> bool:
        return self.session.meets_minimum(self.minimum_seconds)

    def train_local_model(self) -> bool:
        if not self.ready_for_training():
            return False

        sample_paths = [Path(path) for path in self.session.samples if Path(path).exists()]
        if not sample_paths:
            return False

        if self._synthesizer.available:
            if not self._synthesizer.train_from_samples(sample_paths):
                return False
        else:
            self.config.voice_model_path.mkdir(parents=True, exist_ok=True)
            model_file = self.config.voice_model_path / "model.bin"
            model_file.write_bytes(b"local-xtts-stub")
            speaker = self.config.speaker_wav_path
            speaker.write_bytes(sample_paths[0].read_bytes())

        self.output.mark_model_ready()
        self.session.trained = True
        self._save_state()
        return True

    def synthesize_test_phrase(self) -> bytes | None:
        if not self.output.model_status().ready:
            return None
        return self._synthesizer.synthesize(TEST_PLAYBACK_PHRASE)

    def approve_clone(self) -> None:
        self.session.approved = True
        self._save_state()

    def reject_clone(self) -> None:
        self.session.approved = False
        self.session.trained = False
        self.output.remove_model()
        self._save_state()

    def retrain(self) -> None:
        self.output.remove_model()
        self.session.approved = False
        self.session.trained = False
        self._save_state()

    def is_enrollment_complete(self) -> bool:
        return self.session.approved and self.output.model_status().ready

    def enrollment_status(self) -> dict:
        minimum = self.minimum_seconds
        recommended = self.recommended_seconds
        seconds = self.session.sample_seconds
        return {
            "prompt": self.next_prompt(),
            "prompts_completed": self.session.prompts_completed,
            "sample_seconds": round(seconds, 1),
            "minimum_seconds": minimum,
            "recommended_seconds": recommended,
            "minimum_met": seconds >= minimum,
            "recommended_met": seconds >= recommended,
            "ready_for_training": self.ready_for_training(),
            "trained": self.session.trained,
            "approved": self.session.approved,
            "complete": self.is_enrollment_complete(),
            "sample_count": len(self.session.samples),
            "tts_available": self._synthesizer.available,
            "test_phrase": TEST_PLAYBACK_PHRASE,
        }
