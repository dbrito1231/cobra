"""Hybrid rule + LLM router per specs/brain/router.md."""

from __future__ import annotations

import json
import re
from pathlib import Path

from brain.config import BrainConfig
from brain.model_layer import ModelLayer
from brain.models import RouteIntent, RouteResult


GREETING_RE = re.compile(r"^(hi|hello|hey|good morning|good evening|yo)\b", re.IGNORECASE)
SMALL_TALK_RE = re.compile(r"\b(how are you|what's up|nice weather)\b", re.IGNORECASE)
FACT_CHECK_RE = re.compile(r"\b(fact check|verify that|is it true)\b", re.IGNORECASE)
TOOL_RE = re.compile(r"\b(open|run|execute|search|send email|calendar)\b", re.IGNORECASE)
QUESTION_RE = re.compile(r"\?\s*$")


class Router:
    """Classifies intent and selects execution path."""

    def __init__(
        self,
        model: ModelLayer,
        config: BrainConfig,
        *,
        pattern_file: Path | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self._pattern_file = pattern_file
        self._patterns: dict[str, RouteIntent] = {}
        self._load_patterns()

    def route(self, text: str) -> RouteResult:
        learned = self._match_pattern(text)
        if learned is not None:
            return RouteResult(intent=learned, confidence=0.95)

        rule = self._rule_classify(text)
        if rule is not None:
            self._remember(text, rule.intent)
            return rule

        llm = self._llm_classify(text)
        if llm.confidence >= self.config.router_confidence_threshold:
            self._remember(text, llm.intent)
            return llm

        return RouteResult(
            intent=RouteIntent.CLARIFY,
            confidence=llm.confidence,
            clarification_options=self._clarification_options(text),
            clarification_prompt="I'm not sure what you need — which fits best?",
        )

    def _rule_classify(self, text: str) -> RouteResult | None:
        if GREETING_RE.match(text.strip()):
            return RouteResult(intent=RouteIntent.GREETING, confidence=1.0)
        if SMALL_TALK_RE.search(text):
            return RouteResult(intent=RouteIntent.SMALL_TALK, confidence=0.95)
        if FACT_CHECK_RE.search(text):
            return RouteResult(intent=RouteIntent.FACT_CHECK, confidence=0.95)
        if TOOL_RE.search(text):
            return RouteResult(intent=RouteIntent.TOOL, confidence=0.9)
        if QUESTION_RE.search(text):
            return RouteResult(intent=RouteIntent.FACTUAL, confidence=0.85)
        return None

    def _llm_classify(self, text: str) -> RouteResult:
        completion = self.model.complete(
            (
                "Classify intent as one of: greeting, small_talk, factual, tool, "
                f"fact_check, general. Message: {text}"
            ),
            system="Reply with only the intent label.",
            max_tokens=16,
        )
        label = completion.text.lower().strip().replace(" ", "_")
        mapping = {
            "greeting": RouteIntent.GREETING,
            "small_talk": RouteIntent.SMALL_TALK,
            "factual": RouteIntent.FACTUAL,
            "tool": RouteIntent.TOOL,
            "fact_check": RouteIntent.FACT_CHECK,
            "general": RouteIntent.GENERAL,
        }
        intent = mapping.get(label, RouteIntent.GENERAL)
        confidence = 0.5 if completion.offline else 0.8
        return RouteResult(intent=intent, confidence=confidence)

    def _clarification_options(self, text: str) -> list[str]:
        options = ["Answer a factual question", "Run a tool or action", "Just chat"]
        if "?" in text:
            options[0] = f"Answer: {text[:60]}"
        return options[:3]

    def _pattern_key(self, text: str) -> str:
        return " ".join(text.lower().split()[:6])

    def _match_pattern(self, text: str) -> RouteIntent | None:
        return self._patterns.get(self._pattern_key(text))

    def _remember(self, text: str, intent: RouteIntent) -> None:
        self._patterns[self._pattern_key(text)] = intent
        if self._pattern_file is None:
            return
        self._pattern_file.parent.mkdir(parents=True, exist_ok=True)
        serializable = {key: value.value for key, value in self._patterns.items()}
        self._pattern_file.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def _load_patterns(self) -> None:
        if self._pattern_file is None or not self._pattern_file.exists():
            return
        try:
            data = json.loads(self._pattern_file.read_text(encoding="utf-8"))
            self._patterns = {
                key: RouteIntent(value) for key, value in data.items()
            }
        except (json.JSONDecodeError, ValueError):
            self._patterns = {}
