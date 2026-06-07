"""Brain component service — top-level interface for orchestrator integration."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from orchestrator.onboarding import OnboardingManager
    from tools.service import ToolsService
from uuid import uuid4

from chat_ui.models import (
    ApprovalRequestPayload,
    ChatMessage,
    OnboardingStepPayload,
    PipelineStep,
    ProactiveItem,
    SeedConfirmPayload,
    SeedModePayload,
    SeedPromptPayload,
    SeedSummaryReviewPayload,
    WebSocketEvent,
)
from config.reader import ConfigReader
from mcp.service import McpService
from voice.models import TranscribedTextEvent

from brain.config import BrainConfig
from brain.context import ContextBuilder
from brain.input_mode import InputModeLayer
from brain.memory.raw_logs import RawLogStore
from brain.memory.retrieval import MemoryRetriever
from brain.memory.vector import VectorIndex
from brain.memory.wiki import WikiStore
from brain.model_layer import ModelLayer, ModelUnavailableError
from brain.models import HealthStatus, RawLogEntry
from brain.personality import PersonalityMirror
from brain.pipeline import SequentialPipeline
from brain.privacy import PrivacyGate, full_reset
from brain.proactivity import ProactivityEngine
from brain.reasoning import ReasoningEngine
from brain.router import Router
from brain.living_document import LivingDocumentManager
from brain.seed_document import InterviewPhase, SeedDocumentManager
from brain.summarizer import SessionSummarizer
from brain.verification import VerificationPipeline
from brain.wiki_ops import WikiOperations

VoiceDeliver = Callable[[str, dict[str, Any]], Union[Awaitable[None], None]]

SEED_INTERVIEW_TRIGGERS = frozenset(
    {
        "start personality interview",
        "continue personality interview",
    }
)
_OVERRIDE_PATTERN = re.compile(r"^override\s+(.+?):\s*(.+)$", re.IGNORECASE | re.DOTALL)
_REFRESH_PATTERN = re.compile(r"^refresh\s+(.+)$", re.IGNORECASE)


class BrainService:
    """Top-level Brain component initialized in Orchestrator Phase 3."""

    def __init__(
        self,
        config_reader: ConfigReader,
        *,
        mcp_service: McpService | None = None,
        tools_service: ToolsService | None = None,
        audit_outbound: Callable[..., None] | None = None,
        approval_prompt: Callable[..., Union[Awaitable[bool], bool]] | None = None,
        on_voice_deliver: VoiceDeliver | None = None,
        offline: bool | None = None,
        onboarding: OnboardingManager | None = None,
    ) -> None:
        legacy = self._reader_to_legacy(config_reader)
        self.config = BrainConfig.from_config_dict(legacy)
        if offline is not None:
            self.config.offline_mode = offline

        paths = config_reader.storage_paths()
        self.wiki = WikiStore(paths["wiki_dir"])
        self.raw_logs = RawLogStore(paths["memory_dir"])
        self.vector = VectorIndex(paths["memory_dir"] / "vector")
        self.model = ModelLayer(self.config)
        self.seed = SeedDocumentManager(
            self.wiki,
            paths["memory_dir"] / "seed_state.json",
            model=self.model,
        )
        self.living_doc = LivingDocumentManager(
            self.seed,
            self.model,
            paths["wiki_dir"],
        )
        self.seed.set_living_doc(self.living_doc)
        self.privacy = PrivacyGate(approval_prompt=approval_prompt)
        self.wiki_ops = WikiOperations(
            self.wiki,
            self.vector,
            self.model,
            living_doc=self.living_doc,
        )
        self.retriever = MemoryRetriever(self.wiki, self.vector)
        self.personality = PersonalityMirror(
            self.wiki,
            self.model,
            living_doc=self.living_doc,
        )
        self.reasoning = ReasoningEngine(self.model)
        self.router = Router(
            self.model,
            self.config,
            pattern_file=paths["memory_dir"] / "router_patterns.json",
        )
        self.context_builder = ContextBuilder()
        self.input_mode = InputModeLayer()
        self.proactivity = ProactivityEngine()
        self.summarizer = SessionSummarizer(
            self.raw_logs,
            self.model,
            paths["memory_dir"] / "summaries",
        )
        self._mcp_service = mcp_service
        self._tools_service = tools_service
        self.verification = VerificationPipeline(
            self.config,
            self.privacy,
            self.wiki_ops,
            mcp_call=mcp_service.call_mcp if mcp_service else None,
            audit_outbound=audit_outbound,
        )
        self.pipeline = SequentialPipeline(
            self.model,
            self.retriever,
            self.personality,
            self.verification,
            tool_executor=tools_service.execute_tool if tools_service else None,
            approval_events=self._handle_tool_approval,
        )
        self._on_voice_deliver = on_voice_deliver
        self._onboarding = onboarding
        self._initialized = False
        self._response_in_progress = False
        self._pending_events: list[WebSocketEvent] = []

    def initialize(self) -> None:
        for page in self.wiki.list_pages():
            self.vector.upsert(page, self.wiki.read(page.replace(".md", "")))
        self.wiki_ops.lint()
        self._start_tools_session()
        self._initialized = True

    def shutdown(self) -> None:
        self.summarize_session()
        self._initialized = False

    def health(self) -> HealthStatus:
        if not self._initialized:
            return HealthStatus(healthy=False, message="not initialized")
        if self.config.offline_mode:
            return HealthStatus(healthy=True, message="offline mode", degraded=True)
        if self.model.is_available():
            return HealthStatus(healthy=True, message="ok")
        return HealthStatus(
            healthy=True,
            message="LM Studio unreachable — using fallback responses",
            degraded=True,
        )

    async def process_input(
        self,
        text: str,
        *,
        mood: dict[str, Any] | None = None,
        source: str = "text",
    ) -> list[WebSocketEvent]:
        """Primary contract — process user text and return WebSocket events."""

        from voice.models import MoodResult

        mood_obj = MoodResult(**mood) if mood else None
        normalized = self.input_mode.normalize_text(text, mood=mood_obj)

        if normalized.needs_confirmation:
            msg = ChatMessage(sender="cobra", content=normalized.confirmation_prompt)
            return [WebSocketEvent.message(msg)]

        override = self._parse_override(normalized.text)
        if override is not None:
            return self._handle_override(*override)

        pe2_section = self._parse_pe2_refresh(normalized.text)
        if pe2_section is not None:
            return await self._start_pe2_refresh(pe2_section, normalized.text.strip())

        if normalized.text.strip().lower() in SEED_INTERVIEW_TRIGGERS:
            return await self._start_seed_interview(normalized.text.strip())

        blocked = self.onboarding_blocked_reason()
        if blocked and not self.seed_mode_active:
            return await self._onboarding_blocked_events(blocked)

        if self.seed_mode_active:
            return await self._process_seed_input(normalized.text)

        try:
            return await self._run_pipeline(normalized.text, mood_obj)
        except ModelUnavailableError as exc:
            return self._model_unavailable_events(str(exc))

    async def process_voice_event(self, event: TranscribedTextEvent) -> list[WebSocketEvent]:
        normalized = self.input_mode.normalize_voice(event)
        if normalized.needs_confirmation:
            msg = ChatMessage(sender="cobra", content=normalized.confirmation_prompt)
            return [WebSocketEvent.message(msg)]
        override = self._parse_override(normalized.text)
        if override is not None:
            return self._handle_override(*override)
        pe2_section = self._parse_pe2_refresh(normalized.text)
        if pe2_section is not None:
            return await self._start_pe2_refresh(pe2_section, normalized.text.strip())
        if normalized.text.strip().lower() in SEED_INTERVIEW_TRIGGERS:
            return await self._start_seed_interview(normalized.text.strip())
        blocked = self.onboarding_blocked_reason()
        if blocked and not self.seed_mode_active:
            return await self._onboarding_blocked_events(blocked)
        if self.seed_mode_active:
            return await self._process_seed_input(normalized.text)
        try:
            return await self._run_pipeline(normalized.text, event.mood, source="voice")
        except ModelUnavailableError as exc:
            return self._model_unavailable_events(str(exc))

    async def _run_pipeline(
        self,
        text: str,
        mood=None,
        *,
        source: str = "text",
    ) -> list[WebSocketEvent]:
        events: list[WebSocketEvent] = []
        self._response_in_progress = True

        try:
            events.append(WebSocketEvent.pipeline_step(PipelineStep.REASONING))
            self.context_builder.detect_task_shift(text)
            if mood:
                self.context_builder.update_mood(mood)
            else:
                self.context_builder.infer_mood_from_text(text)

            plan = self.reasoning.plan(text)
            route = self.router.route(text)
            context = self.context_builder.build(text, plan=plan, route=route)
            context.route = route
            context.execution_plan = plan

            pipeline_result, step_events = await self.pipeline.run(context)
            events.extend(step_events)

            final_text = self.pipeline.finalize(pipeline_result)
            self._log_exchange(text, final_text, source=source, mood=mood)
            self.personality.log_behavior(text, final_text)

            cobra_msg = ChatMessage(sender="cobra", content=final_text)
            events.append(WebSocketEvent.message(cobra_msg))

            self.proactivity.record_exchange(text, final_text)
            self.proactivity.mark_conversation_complete()
            self.proactivity.mark_silence()
            proactive = self.proactivity.surface_next()
            if proactive:
                events.append(
                    WebSocketEvent.proactive_queue(
                        self.proactivity.queue_count,
                        ProactiveItem(
                            id=proactive.id,
                            preview=proactive.preview,
                            priority=proactive.priority,
                        ),
                    )
                )

            if self.seed.should_prompt_mv3():
                self.proactivity.enqueue_seed_completion()
                self.seed.record_mv3_prompt()
                mv3 = self.proactivity.top_item
                if mv3:
                    events.append(
                        WebSocketEvent.proactive_queue(
                            self.proactivity.queue_count,
                            ProactiveItem(
                                id=mv3.id,
                                preview=mv3.preview,
                                priority=mv3.priority,
                            ),
                        )
                    )

            if self.seed.profile_complete() and self.seed.should_prompt_pe2():
                section = self.seed.stalest_pe2_section()
                if section:
                    self.proactivity.enqueue_pe2_refresh(section)
                    self.seed.record_pe2_prompt()
                    pe2 = self.proactivity.top_item
                    if pe2:
                        events.append(
                            WebSocketEvent.proactive_queue(
                                self.proactivity.queue_count,
                                ProactiveItem(
                                    id=pe2.id,
                                    preview=pe2.preview,
                                    priority=pe2.priority,
                                ),
                            )
                        )

            events.append(WebSocketEvent.seed_mode(self._seed_mode_payload()))

            if self._on_voice_deliver and source == "voice":
                mood_ctx = mood.to_context() if mood else {}
                deliver = self._on_voice_deliver(final_text, mood_ctx)
                if asyncio.iscoroutine(deliver):
                    await deliver

            events.append(WebSocketEvent.pipeline_step(PipelineStep.IDLE))
            return events
        finally:
            self._response_in_progress = False
            events.extend(self._pending_events)
            self._pending_events.clear()

    def summarize_session(self) -> None:
        summary = self.summarizer.summarize_session()
        if summary and summary.meta_summary:
            self.wiki_ops.ingest_session(summary.meta_summary)
        self.proactivity.clear_session_buffer()
        self.context_builder.reset_session()
        self.raw_logs.new_session()
        self._start_tools_session()

    def handle_summarize_event(self, _payload: dict | None = None) -> None:
        self.summarize_session()

    def reset_all_data(self) -> None:
        full_reset(self.config.wiki_dir, self.config.memory_dir, self.config.logs_dir)
        self.wiki = WikiStore(self.config.wiki_dir)
        self.vector = VectorIndex(self.config.memory_dir / "vector")

    def seed_question(self) -> str | None:
        return self.seed.next_question()

    def seed_answer(self, answer: str) -> str | None:
        return self.seed.record_answer(answer)

    @property
    def seed_mode_active(self) -> bool:
        if self._onboarding is not None and not self._onboarding.is_operational():
            if self._onboarding.current_phase().value == "voice":
                return False
        if self.seed.interview_active():
            return True
        return self.seed.needs_seed_gate()

    def personality_ready(self) -> bool:
        return self.seed.profile_complete() or self.personality.is_personality_ready()

    def onboarding_blocked_reason(self) -> str | None:
        if self._onboarding is None or self._onboarding.is_operational():
            return None
        phase = self._onboarding.current_phase().value
        if phase == "voice":
            return "Complete voice enrollment before using C.O.B.R.A."
        if phase == "seed" and self.seed.needs_seed_gate() and not self.seed.interview_active():
            return "Complete the personality interview before using C.O.B.R.A."
        return None

    def onboarding_payload(self) -> dict[str, Any]:
        if self._onboarding is None:
            return {
                "phase": "complete" if self.personality_ready() else "seed",
                "voice_complete": True,
                "personality_complete": self.personality_ready(),
                "operational": self.personality_ready(),
                "blocked_reason": "",
            }
        return self._onboarding.to_payload(blocked_reason=self.onboarding_blocked_reason() or "")

    async def _onboarding_blocked_events(self, reason: str) -> list[WebSocketEvent]:
        return [
            WebSocketEvent.onboarding_step(
                OnboardingStepPayload(
                    phase=self._onboarding.current_phase().value if self._onboarding else "seed",
                    voice_complete=bool(
                        self._onboarding and self._onboarding.data.voice_enrollment_complete
                    ),
                    personality_complete=bool(
                        self._onboarding and self._onboarding.data.personality_enrollment_complete
                    ),
                    operational=False,
                    blocked_reason=reason,
                )
            ),
            WebSocketEvent.message(
                ChatMessage(sender="cobra", content=reason)
            ),
        ]

    async def _maybe_auto_start_seed(self) -> list[WebSocketEvent] | None:
        if self._onboarding is None:
            return None
        if self._onboarding.current_phase().value != "seed":
            return None
        if not self.seed.needs_seed_gate() or self.seed.interview_active():
            return None
        return await self._start_seed_interview("start personality interview")

    def seed_export(self) -> dict[str, str]:
        seed_state = ""
        if self.seed.state_file.exists():
            seed_state = self.seed.state_file.read_text(encoding="utf-8")
        return {
            "you_md": self.wiki.read("you"),
            "seed_state": seed_state,
            "you_history_md": self.living_doc.read_history(),
        }

    async def _start_seed_interview(self, user_text: str) -> list[WebSocketEvent]:
        if self.seed.mvp_complete() and self.seed.optional_stages_remaining():
            turn = self.seed.begin_optional_interview()
        else:
            turn = self.seed.begin_interview()
        return self._seed_turn_to_events(turn, user_text=user_text)

    async def _start_pe2_refresh(self, section: str, user_text: str) -> list[WebSocketEvent]:
        turn = self.seed.begin_pe2_refresh(section)
        return self._seed_turn_to_events(turn, user_text=user_text)

    async def _process_seed_input(self, text: str) -> list[WebSocketEvent]:
        self._response_in_progress = True
        try:
            if (
                self.seed.state.phase == InterviewPhase.ASKING
                and not self.seed.state.awaiting_answer
                and not self.seed.state.session_active
            ):
                if self.seed.mvp_complete() and self.seed.optional_stages_remaining():
                    turn = self.seed.begin_optional_interview()
                else:
                    turn = self.seed.begin_interview()
                user_text = ""
            else:
                turn = self.seed.handle_input(text)
                user_text = text

            return self._seed_turn_to_events(turn, user_text=user_text)
        except ModelUnavailableError as exc:
            return self._model_unavailable_events(str(exc))
        finally:
            self._response_in_progress = False

    def _seed_turn_to_events(self, turn, *, user_text: str) -> list[WebSocketEvent]:
        events: list[WebSocketEvent] = [self._seed_mode_event()]

        for event_data in turn.events:
            event_type = event_data.get("type")
            if event_type == "seed_prompt":
                events.append(
                    WebSocketEvent.seed_prompt(
                        SeedPromptPayload(
                            stage=str(event_data["stage"]),
                            phase=str(event_data["phase"]),
                            content=str(event_data["content"]),
                            question=event_data.get("question"),  # type: ignore[arg-type]
                        )
                    )
                )
            elif event_type == "seed_confirm":
                events.append(
                    WebSocketEvent.seed_confirm(
                        SeedConfirmPayload(
                            stage=str(event_data["stage"]),
                            reflection=str(event_data["reflection"]),
                            question=str(event_data["question"]),
                        )
                    )
                )
            elif event_type == "seed_summary_review":
                events.append(
                    WebSocketEvent.seed_summary_review(
                        SeedSummaryReviewPayload(
                            stage=str(event_data["stage"]),
                            summary=str(event_data["summary"]),
                            prompt=str(event_data["prompt"]),
                        )
                    )
                )

        if user_text and turn.messages:
            self._log_exchange(user_text, "\n\n".join(turn.messages), source="text")

        for message in turn.messages:
            events.append(WebSocketEvent.message(ChatMessage(sender="cobra", content=message)))

        if turn.interview_complete:
            if self.seed.profile_complete():
                if self._onboarding is not None:
                    self._onboarding.mark_personality_complete()
                events.append(
                    WebSocketEvent.seed_mode(
                        SeedModePayload(
                            active=False,
                            resume_label="Interview complete",
                            profile_complete=True,
                            mvp_complete=True,
                        )
                    )
                )
                events.append(
                    WebSocketEvent.onboarding_step_from_dict(self.onboarding_payload())
                )
            elif self.seed.mvp_complete():
                self.seed.end_optional_interview()
                events.append(WebSocketEvent.seed_mode(self._seed_mode_payload()))
            else:
                events.append(
                    WebSocketEvent.seed_mode(
                        SeedModePayload(active=False, resume_label="Interview complete")
                    )
                )

        return events

    def _seed_mode_payload(self) -> SeedModePayload:
        active = self.seed.interview_active()
        optional_remaining = self.seed.optional_stages_remaining()
        mvp_complete = self.seed.mvp_complete()
        needs_resume = (
            not active
            and (
                (not mvp_complete and bool(self.seed.state.completed_stages))
                or (mvp_complete and optional_remaining)
            )
        )
        show_banner = active or needs_resume or self.seed.needs_seed_gate()
        resume = self.seed.resume_label()
        if needs_resume and not resume:
            resume = "Next dimension — resume"
        return SeedModePayload(
            active=show_banner,
            stage=self.seed.state.current_stage.value,
            phase=self.seed.state.phase.value,
            resume_label=resume,
            mvp_complete=mvp_complete,
            optional_remaining=optional_remaining,
            profile_complete=self.seed.profile_complete(),
        )

    def _seed_mode_event(self) -> WebSocketEvent:
        return WebSocketEvent.seed_mode(self._seed_mode_payload())

    def _parse_pe2_refresh(self, text: str) -> str | None:
        stripped = text.strip()
        if stripped.lower() == "pe2 interview":
            return self.seed.stalest_pe2_section()
        match = _REFRESH_PATTERN.match(stripped)
        if not match:
            return None
        section = LivingDocumentManager.resolve_section_name(match.group(1).strip())
        return section

    def _parse_override(self, text: str) -> tuple[str, str] | None:
        match = _OVERRIDE_PATTERN.match(text.strip())
        if not match:
            return None
        section = LivingDocumentManager.resolve_section_name(match.group(1))
        if section is None:
            return None
        return section, match.group(2).strip()

    def _handle_override(self, section: str, content: str) -> list[WebSocketEvent]:
        self.living_doc.apply_override(section, content)
        message = (
            f"Got it — I've updated **{section}** with your override. "
            "That section is now authoritative and won't be auto-updated from sessions."
        )
        return [
            WebSocketEvent.message(ChatMessage(sender="cobra", content=message)),
            WebSocketEvent.seed_mode(self._seed_mode_payload()),
        ]

    def _model_unavailable_events(self, message: str) -> list[WebSocketEvent]:
        wait_message = message or ModelLayer.LM_STUDIO_WAIT_MESSAGE
        return [
            WebSocketEvent.lm_studio_wait(waiting=True, message=wait_message),
            WebSocketEvent.message(
                ChatMessage(sender="cobra", content=wait_message)
            ),
        ]

    async def deliver_proactive(self, item: ProactiveItem) -> list[WebSocketEvent]:
        """Deliver a surfaced proactive observation to the user."""

        text = item.preview
        cobra_msg = ChatMessage(sender="cobra", content=text)
        events: list[WebSocketEvent] = [WebSocketEvent.message(cobra_msg)]
        if self._on_voice_deliver:
            deliver = self._on_voice_deliver(text, {})
            if asyncio.iscoroutine(deliver):
                await deliver
        return events

    @property
    def response_in_progress(self) -> bool:
        return self._response_in_progress

    def _log_exchange(self, user_text: str, response: str, *, source: str, mood=None) -> None:
        mood_data = mood.to_context() if mood and hasattr(mood, "to_context") else None
        session_id = self.raw_logs.session_id
        self.raw_logs.append(
            RawLogEntry(
                session_id=session_id,
                sender="user",
                content=user_text,
                timestamp=datetime.now(timezone.utc),
                mood={"source": source, **(mood_data or {})},
            )
        )
        self.raw_logs.append(
            RawLogEntry(
                session_id=session_id,
                sender="cobra",
                content=response,
                timestamp=datetime.now(timezone.utc),
            )
        )

    def _handle_tool_approval(self, event: dict) -> None:
        payload = ApprovalRequestPayload.from_tools_approval(event)
        self._pending_events.append(WebSocketEvent.approval_request(payload))

    def _start_tools_session(self) -> None:
        """Reset per-session sandbox override at session boundaries."""

        if self._tools_service is None:
            return
        self._tools_service.set_session_sandbox(None)

    @staticmethod
    def _reader_to_legacy(reader: ConfigReader) -> dict:
        profile = reader.active_profile()
        return {
            "model": profile.model.model_dump(),
            "api_keys": profile.api_keys.model_dump(),
            "storage": profile.storage.model_dump(),
        }
