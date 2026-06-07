"""Tests for first-run onboarding gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.seed_document import InterviewStage
from brain.service import BrainService
from config.models import CobraConfig, ProfileConfig
from config.reader import ConfigReader
from orchestrator.onboarding import OnboardingManager, OnboardingPhase
from voice.config import VoiceConfig
from voice.output import VoiceOutput
from voice.cloning import VoiceCloningManager
from voice.recorder import pcm_to_wav
from voice.service import VoiceService


@pytest.fixture
def cobra_dir(tmp_path: Path) -> Path:
    path = tmp_path / "cobra"
    path.mkdir()
    return path


@pytest.fixture
def config_reader(cobra_dir: Path) -> ConfigReader:
    config = CobraConfig(
        profiles={
            "default": ProfileConfig(
                storage={
                    "wiki_dir": str(cobra_dir / "wiki"),
                    "memory_dir": str(cobra_dir / "memory"),
                    "logs_dir": str(cobra_dir / "logs"),
                    "backups_dir": str(cobra_dir / "backups"),
                }
            )
        }
    )
    return ConfigReader(config)


@pytest.fixture
def brain_service(config_reader: ConfigReader, cobra_dir: Path) -> BrainService:
    onboarding = OnboardingManager(cobra_dir / "onboarding_state.json")
    return BrainService(config_reader, offline=True, onboarding=onboarding)


@pytest.fixture
def voice_service(cobra_dir: Path) -> VoiceService:
    config = VoiceConfig(
        voice_model_path=cobra_dir / "voice",
        minimum_enrollment_seconds=5.0,
    )
    return VoiceService(config)


def _complete_voice(voice: VoiceService) -> None:
    sample_path = voice.config.voice_model_path / "samples" / "sample_0000.wav"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_bytes(pcm_to_wav(b"\x00\x00" * 8000, sample_rate=16000))
    voice.cloning.session.samples = [str(sample_path)]
    voice.cloning.session.sample_seconds = voice.config.minimum_enrollment_seconds
    voice.cloning.train_local_model()
    voice.cloning.approve_clone()


class TestOnboardingManager:
    def test_starts_at_voice_when_empty(
        self,
        brain_service: BrainService,
        voice_service: VoiceService,
        cobra_dir: Path,
    ) -> None:
        onboarding = OnboardingManager(cobra_dir / "onboarding_state.json")
        onboarding.sync(voice=voice_service, brain=brain_service, needs_wizard=False)
        assert onboarding.current_phase() == OnboardingPhase.VOICE

    def test_moves_to_seed_after_voice(
        self,
        brain_service: BrainService,
        voice_service: VoiceService,
        cobra_dir: Path,
    ) -> None:
        onboarding = OnboardingManager(cobra_dir / "onboarding_state.json")
        _complete_voice(voice_service)
        onboarding.sync(voice=voice_service, brain=brain_service, needs_wizard=False)
        assert onboarding.current_phase() == OnboardingPhase.SEED

    def test_operational_when_both_complete(
        self,
        brain_service: BrainService,
        voice_service: VoiceService,
        cobra_dir: Path,
    ) -> None:
        onboarding = OnboardingManager(cobra_dir / "onboarding_state.json")
        _complete_voice(voice_service)
        brain_service.seed.state.completed_stages = [
            stage.value for stage in InterviewStage
        ]
        brain_service.seed._save_state()
        onboarding.sync(voice=voice_service, brain=brain_service, needs_wizard=False)
        assert onboarding.is_operational()


class TestBrainOnboardingGate:
    @pytest.mark.asyncio
    async def test_blocks_pipeline_until_voice_complete(
        self, brain_service: BrainService, voice_service: VoiceService, cobra_dir: Path
    ) -> None:
        brain_service.initialize()
        onboarding = OnboardingManager(cobra_dir / "onboarding_state.json")
        onboarding.sync(voice=voice_service, brain=brain_service, needs_wizard=False)
        events = await brain_service.process_input("Hello")
        types = {event.type for event in events}
        assert "onboarding_step" in types
        assert "pipeline_step" not in types

    @pytest.mark.asyncio
    async def test_seed_gate_requires_all_stages(
        self, brain_service: BrainService, voice_service: VoiceService
    ) -> None:
        brain_service.initialize()
        _complete_voice(voice_service)
        assert brain_service._onboarding is not None
        brain_service._onboarding.sync(
            voice=voice_service,
            brain=brain_service,
            needs_wizard=False,
        )
        assert brain_service.seed.needs_seed_gate()
        assert brain_service.seed_mode_active
