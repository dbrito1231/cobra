"""Brain component data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class RouteIntent(str, Enum):
    """Router classification outcomes."""

    GREETING = "greeting"
    SMALL_TALK = "small_talk"
    FACTUAL = "factual"
    TOOL = "tool"
    FACT_CHECK = "fact_check"
    CLARIFY = "clarify"
    GENERAL = "general"


class PipelineStage(str, Enum):
    """Sequential pipeline stages P1–P6."""

    MEMORY = "memory_retrieval"
    TOOLS = "tool_execution"
    VERIFICATION = "verification"
    PERSONALITY = "personality_mirror"
    SYNTHESIS = "response_synthesis"


class VerificationOutcome(str, Enum):
    """Verification pipeline branch results."""

    CORRECTION = "correction"
    CONFLICT = "conflict"
    SUPPRESSED = "suppressed"
    SKIPPED = "skipped"


@dataclass
class HealthStatus:
    healthy: bool = True
    message: str = "ok"
    degraded: bool = False


@dataclass
class ExecutionPlan:
    """Silent reasoning output — blueprint for the pipeline."""

    retrieve_topics: list[str] = field(default_factory=list)
    needs_tools: bool = False
    tool_hints: list[str] = field(default_factory=list)
    may_need_verification: bool = False
    response_framing: str = ""
    claim_to_verify: str | None = None


@dataclass
class RouteResult:
    """Router output after classification."""

    intent: RouteIntent
    confidence: float
    clarification_options: list[str] = field(default_factory=list)
    clarification_prompt: str = ""


@dataclass
class SharedContext:
    """Read-only shared state for a single pipeline run."""

    timestamp: datetime
    current_task: str | None = None
    mood: str = "neutral"
    energy: float = 0.5
    user_text: str = ""
    execution_plan: ExecutionPlan | None = None
    route: RouteResult | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "current_task": self.current_task,
            "mood": self.mood,
            "energy": self.energy,
        }


@dataclass
class MemoryHit:
    page: str
    content: str
    score: float = 0.0


@dataclass
class PipelineResult:
    """Accumulated outputs from pipeline stages."""

    memory_hits: list[MemoryHit] = field(default_factory=list)
    tool_outputs: list[Any] = field(default_factory=list)
    verification: VerificationOutcome = VerificationOutcome.SKIPPED
    verification_detail: str = ""
    personality_filtered: str = ""
    synthesized: str = ""
    can_answer: bool = True
    failure_suggestions: list[str] = field(default_factory=list)


@dataclass
class RawLogEntry:
    session_id: str
    sender: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    mood: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "mood": self.mood,
        }


@dataclass
class SessionSummary:
    session_id: str
    segments: list[str] = field(default_factory=list)
    meta_summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProactiveObservation:
    id: str = field(default_factory=lambda: str(uuid4()))
    preview: str = ""
    priority: int = 0
    trigger: str = "pattern"


@dataclass
class PrivacyDecision:
    allowed: bool
    sanitized_query: str = ""
    reason: str = ""
    requires_approval: bool = False
