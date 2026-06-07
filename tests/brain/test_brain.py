"""Tests for the Brain component."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.config import BrainConfig
from brain.input_mode import InputModeLayer
from brain.memory.raw_logs import RawLogStore
from brain.memory.vector import VectorIndex
from brain.memory.wiki import WikiStore
from brain.model_layer import ModelLayer, ModelUnavailableError
from brain.models import RawLogEntry
from brain.privacy import PrivacyGate, contains_personal_context, sanitize_topic
from brain.reasoning import ReasoningEngine
from brain.router import Router
from brain.seed_document import InterviewPhase, MVP_STAGES, SeedDocumentManager
from brain.service import BrainService
from brain.summarizer import SessionSummarizer
from chat_ui.models import WebSocketEvent
from config.models import CobraConfig, ProfileConfig
from config.reader import ConfigReader
from voice.models import MoodResult, TranscribedTextEvent


@pytest.fixture
def brain_dirs(tmp_path: Path) -> dict[str, Path]:
    wiki = tmp_path / "wiki"
    memory = tmp_path / "memory"
    logs = tmp_path / "logs"
    for path in (wiki, memory, logs):
        path.mkdir()
    return {"wiki_dir": wiki, "memory_dir": memory, "logs_dir": logs}


@pytest.fixture
def config_reader(brain_dirs: dict[str, Path]) -> ConfigReader:
    config = CobraConfig(
        profiles={
            "default": ProfileConfig(
                storage={
                    "wiki_dir": str(brain_dirs["wiki_dir"]),
                    "memory_dir": str(brain_dirs["memory_dir"]),
                    "logs_dir": str(brain_dirs["logs_dir"]),
                    "backups_dir": str(brain_dirs["memory_dir"] / "backups"),
                }
            )
        }
    )
    return ConfigReader(config)


@pytest.fixture
def brain_service(config_reader: ConfigReader) -> BrainService:
    return BrainService(config_reader, offline=True)


def mark_personality_ready(service: BrainService) -> None:
    service.seed.state.completed_stages = [stage.value for stage in MVP_STAGES]
    service.seed._save_state()
    content = service.wiki.read("you")
    content = content.replace("(To be filled from seed document interview)", "Direct and concise.")
    service.wiki.write("you", content)


class TestPrivacy:
    def test_sanitize_topic(self) -> None:
        result = sanitize_topic("Email user@example.com about sleep")
        assert "[email]" in result
        assert "user@example.com" not in result

    def test_detects_personal_context(self) -> None:
        assert contains_personal_context("My name is Damian and I code late")

    @pytest.mark.asyncio
    async def test_blocks_without_approval(self) -> None:
        gate = PrivacyGate()
        decision = await gate.screen_outbound(
            "claude",
            "Damian codes late at night and has sleep issues",
        )
        assert not decision.allowed

    @pytest.mark.asyncio
    async def test_allows_after_user_approval(self) -> None:
        from orchestrator.approval_wait import ApprovalWaitRegistry

        waits = ApprovalWaitRegistry()
        pending: dict[str, str] = {}

        async def approval_prompt(destination: str, reason: str, summary: str) -> bool:
            event_id = "brain-test-event"
            pending["event_id"] = event_id
            return await waits.register(event_id)

        gate = PrivacyGate(approval_prompt=approval_prompt)
        task = asyncio.create_task(
            gate.screen_outbound(
                "claude",
                "Damian codes late at night and has sleep issues",
            )
        )
        await asyncio.sleep(0.01)
        waits.resolve(pending["event_id"], True)
        decision = await task
        assert decision.allowed
        assert decision.sanitized_query


class TestInputMode:
    def test_normalizes_text(self) -> None:
        layer = InputModeLayer()
        result = layer.normalize_text("  hello   world  ")
        assert result.text == "hello world"
        assert not result.needs_confirmation

    def test_low_confidence_voice(self) -> None:
        layer = InputModeLayer()
        event = TranscribedTextEvent(text="maybe hello", mood=MoodResult(), confidence=0.2)
        result = layer.normalize_voice(event)
        assert result.needs_confirmation


class TestMemory:
    def test_raw_log_append_only(self, brain_dirs: dict[str, Path]) -> None:
        store = RawLogStore(brain_dirs["memory_dir"])
        store.append(
            RawLogEntry(session_id=store.session_id, sender="user", content="hello")
        )
        entries = store.read_session()
        assert len(entries) == 1
        assert entries[0].content == "hello"

    def test_wiki_layout(self, brain_dirs: dict[str, Path]) -> None:
        wiki = WikiStore(brain_dirs["wiki_dir"])
        pages = wiki.list_pages()
        assert "you.md" in pages
        assert "index.md" in pages

    def test_vector_search(self, brain_dirs: dict[str, Path]) -> None:
        index = VectorIndex(brain_dirs["memory_dir"] / "vector")
        index.upsert("topics.md", "Python asyncio patterns and event loops")
        hits = index.search("asyncio")
        assert hits
        assert hits[0][0] == "topics.md"


class TestRouter:
    def test_greeting_fast_path(self, brain_dirs: dict[str, Path]) -> None:
        config = BrainConfig.from_config_dict(
            {"storage": {"wiki_dir": str(brain_dirs["wiki_dir"])}}
        )
        config.offline_mode = True
        router = Router(ModelLayer(config), config)
        result = router.route("Hello there")
        assert result.intent.value == "greeting"
        assert result.confidence >= 0.9


class TestReasoning:
    def test_detects_fact_check(self, brain_dirs: dict[str, Path]) -> None:
        config = BrainConfig.from_config_dict({})
        config.offline_mode = True
        engine = ReasoningEngine(ModelLayer(config))
        plan = engine.plan("Can you fact check whether the earth is flat?")
        assert plan.may_need_verification


class TestSummarizer:
    def test_summarize_session(self, brain_dirs: dict[str, Path]) -> None:
        config = BrainConfig.from_config_dict(
            {"storage": {"memory_dir": str(brain_dirs["memory_dir"])}}
        )
        config.offline_mode = True
        raw = RawLogStore(brain_dirs["memory_dir"])
        raw.append(RawLogEntry(session_id=raw.session_id, sender="user", content="Hi"))
        raw.append(
            RawLogEntry(session_id=raw.session_id, sender="cobra", content="Hello!")
        )
        summarizer = SessionSummarizer(
            raw,
            ModelLayer(config),
            brain_dirs["memory_dir"] / "summaries",
        )
        summary = summarizer.summarize_session()
        assert summary is not None
        assert summary.meta_summary


class TestModelLayer:
    def test_offline_complete(self, brain_dirs: dict[str, Path]) -> None:
        config = BrainConfig.from_config_dict({})
        config.offline_mode = True
        model = ModelLayer(config)
        result = model.complete("summarize this session")
        assert result.offline
        assert result.text

    def test_unavailable_raises_when_not_offline(self, brain_dirs: dict[str, Path]) -> None:
        import httpx

        config = BrainConfig.from_config_dict({})
        config.offline_mode = False
        model = ModelLayer(config)
        with patch(
            "brain.model_layer.httpx.post",
            side_effect=httpx.ConnectError("connection refused"),
        ):
            with pytest.raises(ModelUnavailableError):
                model.complete("hello")


class TestSeedDocument:
    def test_state_machine_confirm_and_store(self, brain_dirs: dict[str, Path]) -> None:
        wiki = WikiStore(brain_dirs["wiki_dir"])
        config = BrainConfig.from_config_dict(
            {"storage": {"wiki_dir": str(brain_dirs["wiki_dir"])}}
        )
        config.offline_mode = True
        seed = SeedDocumentManager(
            wiki,
            brain_dirs["memory_dir"] / "seed_state.json",
            model=ModelLayer(config),
        )

        open_turn = seed.begin_interview()
        assert open_turn.events[0]["type"] == "seed_prompt"
        assert seed.state.awaiting_answer

        reflect_turn = seed.handle_input("I prefer direct communication.")
        assert reflect_turn.phase == InterviewPhase.CONFIRMING
        assert reflect_turn.events[0]["type"] == "seed_confirm"

        next_turn = seed.handle_input("yes")
        assert next_turn.events[0]["type"] == "seed_prompt"

        seed.handle_input("Short messages work best.")
        review_turn = seed.handle_input("yes")
        assert review_turn.phase == InterviewPhase.REVIEW
        assert review_turn.events[0]["type"] == "seed_summary_review"

        stored_turn = seed.handle_input("approve")
        assert stored_turn.stored
        you = wiki.read("you")
        assert "direct communication" in you.lower() or "short messages" in you.lower()
        assert "(To be filled from seed document interview)" not in you.split("## Decision-Making")[0]

    def test_summary_not_stored_without_approval(self, brain_dirs: dict[str, Path]) -> None:
        wiki = WikiStore(brain_dirs["wiki_dir"])
        seed = SeedDocumentManager(wiki, brain_dirs["memory_dir"] / "seed_state.json")
        seed.begin_interview()
        seed.handle_input("Direct and brief.")
        seed.handle_input("yes")
        seed.handle_input("Keep messages short.")
        review = seed.handle_input("yes")
        assert review.phase == InterviewPhase.REVIEW
        you_before = wiki.read("you")
        assert seed.state.pending_summary
        assert "(To be filled from seed document interview)" in you_before


class TestBrainService:
    def test_initialize_and_health(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        health = brain_service.health()
        assert health.healthy
        brain_service.shutdown()

    @pytest.mark.asyncio
    async def test_process_input_returns_events(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        mark_personality_ready(brain_service)
        events = await brain_service.process_input("Hello")
        types = {event.type for event in events}
        assert "message" in types
        assert "pipeline_step" in types
        brain_service.shutdown()

    @pytest.mark.asyncio
    async def test_process_input_logs_raw(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        mark_personality_ready(brain_service)
        await brain_service.process_input("What is Python?")
        entries = brain_service.raw_logs.read_session()
        assert len(entries) >= 2
        brain_service.shutdown()

    @pytest.mark.asyncio
    async def test_seed_mode_routes_before_pipeline(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        assert brain_service.seed_mode_active
        events = await brain_service.process_input("Let's begin")
        types = {event.type for event in events}
        assert "seed_mode" in types
        assert "seed_prompt" in types
        assert "pipeline_step" not in types
        brain_service.shutdown()

    @pytest.mark.asyncio
    async def test_seed_interview_flow_via_process_input(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        await brain_service.process_input("start")
        await brain_service.process_input("I prefer direct communication.")
        confirm_events = await brain_service.process_input("yes")
        types = {event.type for event in confirm_events}
        assert "seed_confirm" in types or "seed_prompt" in types
        brain_service.shutdown()

    def test_seed_interview_legacy_helpers(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        brain_service.seed.begin_interview()
        question = brain_service.seed_question()
        assert question
        brain_service.seed_answer("I prefer direct communication.")
        assert brain_service.seed.state.phase == InterviewPhase.CONFIRMING
        brain_service.shutdown()

    @pytest.mark.asyncio
    async def test_model_unavailable_returns_wait_events(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        mark_personality_ready(brain_service)
        with patch.object(
            brain_service.model,
            "complete",
            side_effect=ModelUnavailableError("LM Studio is unreachable."),
        ):
            events = await brain_service.process_input("Hello")
        types = {event.type for event in events}
        assert "lm_studio_wait" in types
        assert "message" in types
        brain_service.shutdown()

    def test_summarize_on_shutdown(self, brain_service: BrainService) -> None:
        brain_service.initialize()
        brain_service.raw_logs.append(
            RawLogEntry(
                session_id=brain_service.raw_logs.session_id,
                sender="user",
                content="Discussed project planning",
            )
        )
        brain_service.shutdown()
        assert (brain_service.config.wiki_dir / "topics.md").exists()


class TestSeedWebSocketEvents:
    def test_seed_event_factories(self) -> None:
        from chat_ui.models import SeedConfirmPayload, SeedPromptPayload, SeedSummaryReviewPayload

        prompt = WebSocketEvent.seed_prompt(
            SeedPromptPayload(stage="Communication Style", phase="asking", content="Intro", question="Q?")
        )
        assert prompt.type == "seed_prompt"
        confirm = WebSocketEvent.seed_confirm(
            SeedConfirmPayload(stage="Communication Style", reflection="You prefer direct.", question="Yes?")
        )
        assert confirm.type == "seed_confirm"
        review = WebSocketEvent.seed_summary_review(
            SeedSummaryReviewPayload(stage="Communication Style", summary="Summary", prompt="Approve?")
        )
        assert review.type == "seed_summary_review"
