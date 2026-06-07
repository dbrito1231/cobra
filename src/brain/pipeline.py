"""Sequential execution pipeline P1–P6."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Union

from chat_ui.models import ApprovalRequestPayload, PipelineStep, WebSocketEvent
from tools import execute_tool
from tools.models import ToolCall

from brain.failure import FailureHandler
from brain.memory.retrieval import MemoryRetriever
from brain.model_layer import ModelLayer
from brain.models import (
    PipelineResult,
    RouteIntent,
    SharedContext,
    VerificationOutcome,
)
from brain.personality import PersonalityMirror
from brain.verification import VerificationPipeline

ToolExecutor = Callable[[ToolCall], Any]


class SequentialPipeline:
    """Runs memory → tools → verification → personality → synthesis."""

    def __init__(
        self,
        model: ModelLayer,
        retriever: MemoryRetriever,
        personality: PersonalityMirror,
        verification: VerificationPipeline,
        *,
        tool_executor: ToolExecutor | None = None,
        approval_events: Callable[[dict], None] | None = None,
    ) -> None:
        self.model = model
        self.retriever = retriever
        self.personality = personality
        self.verification = verification
        self.failure = FailureHandler()
        self._tool_executor = tool_executor or execute_tool
        self._approval_events = approval_events

    async def run(
        self,
        context: SharedContext,
    ) -> tuple[PipelineResult, list[WebSocketEvent]]:
        events: list[WebSocketEvent] = []
        result = PipelineResult()
        route = context.route
        plan = context.execution_plan
        text = context.user_text

        if route and route.intent == RouteIntent.CLARIFY:
            options = "\n".join(f"- {opt}" for opt in route.clarification_options)
            result.synthesized = f"{route.clarification_prompt}\n{options}"
            result.personality_filtered = result.synthesized
            result.can_answer = True
            return result, events

        if route and route.intent in {RouteIntent.GREETING, RouteIntent.SMALL_TALK}:
            result.synthesized = self._greeting_response(route.intent, context)
            result.personality_filtered = self.personality.apply(result.synthesized, context)
            result.can_answer = True
            return result, events

        events.append(WebSocketEvent.pipeline_step(PipelineStep.MEMORY_RETRIEVAL))
        result.memory_hits = self.retriever.retrieve(text, plan)

        events.append(WebSocketEvent.pipeline_step(PipelineStep.TOOL_EXECUTION))
        if plan and plan.needs_tools:
            result.tool_outputs = await self._run_tools(plan, events)

        needs_verify = (
            route
            and route.intent == RouteIntent.FACT_CHECK
            or (plan and plan.may_need_verification and plan.claim_to_verify)
        )
        if needs_verify and plan and plan.claim_to_verify:
            events.append(WebSocketEvent.pipeline_step(PipelineStep.VERIFICATION))
            outcome, detail = await self.verification.verify(plan.claim_to_verify)
            result.verification = outcome
            result.verification_detail = detail

        events.append(WebSocketEvent.pipeline_step(PipelineStep.PERSONALITY_MIRROR))
        draft = self._synthesize(text, result, context)
        result.synthesized = draft
        result.personality_filtered = self.personality.apply(draft, context)

        events.append(WebSocketEvent.pipeline_step(PipelineStep.RESPONSE_SYNTHESIS))
        result.can_answer = bool(result.personality_filtered.strip()) and (
            result.verification != VerificationOutcome.SUPPRESSED or not needs_verify
        )
        if not result.can_answer:
            result.failure_suggestions = [
                "Try rephrasing with a narrower question.",
                "Ask me to fact-check a specific claim.",
                "Check verified facts in the wiki browser.",
            ]

        return result, events

    async def _run_tools(
        self,
        plan,
        events: list[WebSocketEvent],
    ) -> list[Any]:
        from tools.models import ApprovalEvent

        outputs: list[Any] = []
        for hint in plan.tool_hints:
            call = ToolCall(tool_name=hint, params={"query": plan.response_framing})
            events.append(
                WebSocketEvent.pipeline_step(PipelineStep.TOOL_EXECUTION, tool_name=hint)
            )
            tool_result = self._tool_executor(call)
            if hasattr(tool_result, "__await__"):
                tool_result = await tool_result  # type: ignore[misc]
            if isinstance(tool_result, ApprovalEvent):
                if self._approval_events:
                    self._approval_events(tool_result.to_dict())
                outputs.append(tool_result)
                continue
            outputs.append(tool_result)
        return outputs

    def _synthesize(self, text: str, result: PipelineResult, context: SharedContext) -> str:
        memory_context = "\n\n".join(
            f"[{hit.page}]\n{hit.content[:500]}" for hit in result.memory_hits[:3]
        )
        if result.verification == VerificationOutcome.CORRECTION:
            return result.verification_detail
        if result.verification == VerificationOutcome.CONFLICT:
            return (
                "I found conflicting sources on that claim:\n"
                f"{result.verification_detail}\n"
                "Which source would you like to trust?"
            )

        prompt = (
            f"User: {text}\n\nMemory:\n{memory_context or '(none)'}\n\n"
            f"Framing: {context.execution_plan.response_framing if context.execution_plan else ''}"
        )
        completion = self.model.complete(prompt, max_tokens=512)
        return completion.text.strip()

    @staticmethod
    def _greeting_response(intent: RouteIntent, context: SharedContext) -> str:
        if intent == RouteIntent.GREETING:
            return "Hello! How can I help you today?"
        mood = context.mood
        if mood == "busy":
            return "Doing well — I'll keep it brief. What do you need?"
        return "I'm here and ready when you are."

    def finalize(self, result: PipelineResult) -> str:
        return self.failure.finalize(result)
