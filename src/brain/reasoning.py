"""Internal reasoning — silent think-first planning."""

from __future__ import annotations

import re

from brain.model_layer import ModelLayer
from brain.models import ExecutionPlan


FACT_CHECK_RE = re.compile(
    r"\b(fact check|verify|is it true|did .+ really)\b",
    re.IGNORECASE,
)
CLAIM_RE = re.compile(
    r"\b(is|are|was|were|will|has|have)\b.+\?",
    re.IGNORECASE,
)
TOOL_RE = re.compile(
    r"\b(open|run|execute|search|find file|send|email|calendar)\b",
    re.IGNORECASE,
)


class ReasoningEngine:
    """Produces execution plans before routing and pipeline execution."""

    def __init__(self, model: ModelLayer) -> None:
        self.model = model

    def plan(self, text: str) -> ExecutionPlan:
        lowered = text.lower()
        plan = ExecutionPlan(response_framing="Respond clearly and helpfully.")

        if FACT_CHECK_RE.search(text):
            plan.may_need_verification = True
            plan.claim_to_verify = text
            plan.response_framing = "Verify claim before responding."

        elif CLAIM_RE.search(text):
            plan.may_need_verification = True
            plan.claim_to_verify = text

        if TOOL_RE.search(text):
            plan.needs_tools = True
            plan.tool_hints = self._extract_tool_hints(lowered)

        plan.retrieve_topics = self._extract_topics(text)

        if len(text.split()) > 12 and not plan.retrieve_topics:
            completion = self.model.complete(
                f"List 3 retrieval topics for this message (comma-separated): {text}",
                system="Return only comma-separated topics.",
                max_tokens=64,
            )
            plan.retrieve_topics = [
                item.strip() for item in completion.text.split(",") if item.strip()
            ][:3]

        if not plan.response_framing:
            completion = self.model.complete(
                f"One sentence on how to frame a response to: {text}",
                max_tokens=64,
            )
            plan.response_framing = completion.text

        return plan

    @staticmethod
    def _extract_topics(text: str) -> list[str]:
        stop = {"the", "a", "an", "is", "are", "what", "how", "why", "when", "where", "who"}
        words = [word.strip(".,?!") for word in text.lower().split()]
        topics = [word for word in words if len(word) > 3 and word not in stop]
        return topics[:5]

    @staticmethod
    def _extract_tool_hints(text: str) -> list[str]:
        hints: list[str] = []
        if "open" in text:
            hints.append("app_control")
        if "run" in text or "execute" in text:
            hints.append("code_execution")
        if "search" in text or "find" in text:
            hints.append("web_search")
        if "email" in text or "send" in text:
            hints.append("communication")
        return hints or ["general"]
