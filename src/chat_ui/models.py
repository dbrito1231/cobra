"""WebSocket and REST event models for the Chat UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class PipelineStep(str, Enum):
    """Brain pipeline steps mapped to UI labels."""

    IDLE = "idle"
    REASONING = "reasoning"
    MEMORY_RETRIEVAL = "memory_retrieval"
    TOOL_EXECUTION = "tool_execution"
    VERIFICATION = "verification"
    PERSONALITY_MIRROR = "personality_mirror"
    RESPONSE_SYNTHESIS = "response_synthesis"

    def label(self, tool_name: str | None = None) -> str:
        labels = {
            PipelineStep.IDLE: "Idle",
            PipelineStep.REASONING: "Thinking...",
            PipelineStep.MEMORY_RETRIEVAL: "Searching memory...",
            PipelineStep.TOOL_EXECUTION: f"Running tool: {tool_name or 'unknown'}",
            PipelineStep.VERIFICATION: "Verifying claim...",
            PipelineStep.PERSONALITY_MIRROR: "Composing response...",
            PipelineStep.RESPONSE_SYNTHESIS: "Finalizing...",
        }
        return labels[self]


class VoiceState(str, Enum):
    """Voice indicator states for the top bar."""

    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"


class McpStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    VALIDATING = "validating"


@dataclass
class ChatMessage:
    """A single exchange entry in the current session."""

    id: str = field(default_factory=lambda: str(uuid4()))
    sender: str = "user"
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatMessage":
        ts = data.get("timestamp")
        timestamp = (
            datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.now(timezone.utc)
        )
        return cls(
            id=data.get("id", str(uuid4())),
            sender=data.get("sender", "user"),
            content=data.get("content", ""),
            timestamp=timestamp,
        )


@dataclass
class McpServerStatus:
    name: str
    status: McpStatus

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status.value}


@dataclass
class ProactiveItem:
    id: str
    preview: str
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentHealthEntry:
    name: str
    state: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailurePromptPayload:
    event_id: str
    component: str
    state: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeedPromptPayload:
    stage: str
    phase: str
    content: str
    question: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeedConfirmPayload:
    stage: str
    reflection: str
    question: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeedSummaryReviewPayload:
    stage: str
    summary: str
    prompt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeedModePayload:
    active: bool
    stage: str = ""
    phase: str = ""
    resume_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sanitize_approval_summary(params: dict[str, Any]) -> str:
    """Topic-level preview for approval cards — no raw personal data."""

    import re

    topic_keys = ("query", "topic", "subject", "operation", "path", "tool_name")
    parts: list[str] = []
    for key in topic_keys:
        value = params.get(key)
        if value:
            parts.append(f"{key}: {value}")
    if not parts:
        parts.append("operation only")
    summary = "; ".join(parts)
    summary = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", summary)
    summary = re.sub(r"/Users/[^/\s]+", "[home]", summary)
    return summary


@dataclass
class ApprovalRequestPayload:
    """Inline approval card payload (what / why / data)."""

    event_id: str
    what: str
    why: str
    data_summary: str
    action_type: str | None = None
    code_preview: str | None = None
    draft_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_tools_approval(cls, event: dict[str, Any]) -> "ApprovalRequestPayload":
        tool_call = event.get("tool_call") or {}
        params = dict(tool_call.get("params") or {})
        action_type = event.get("action_type")
        tool_name = tool_call.get("tool_name", "unknown")

        if action_type == "code_execution":
            what = f"Run code via: {tool_name}"
        elif action_type == "communication":
            what = f"Draft message via: {tool_name}"
        else:
            what = f"Run tool: {tool_name}"

        return cls(
            event_id=event.get("event_id", str(uuid4())),
            what=what,
            why=event.get("explanation", "Approval required before proceeding."),
            data_summary=_sanitize_approval_summary(params),
            action_type=action_type,
            code_preview=event.get("code_preview"),
            draft_content=event.get("draft_content"),
        )


@dataclass
class WebSocketEvent:
    """Envelope for all realtime pushes to the browser."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "payload": self.payload}

    @classmethod
    def pipeline_step(
        cls,
        step: PipelineStep,
        *,
        tool_name: str | None = None,
        started_at: datetime | None = None,
        message_id: str | None = None,
    ) -> "WebSocketEvent":
        return cls(
            type="pipeline_step",
            payload={
                "step": step.value,
                "label": step.label(tool_name),
                "tool_name": tool_name,
                "started_at": (started_at or datetime.now(timezone.utc)).isoformat(),
                "message_id": message_id,
            },
        )

    @classmethod
    def voice_state(cls, state: VoiceState) -> "WebSocketEvent":
        return cls(type="voice_state", payload={"state": state.value})

    @classmethod
    def mcp_status(cls, servers: list[McpServerStatus]) -> "WebSocketEvent":
        return cls(
            type="mcp_status",
            payload={"servers": [server.to_dict() for server in servers]},
        )

    @classmethod
    def proactive_queue(
        cls, count: int, top_item: ProactiveItem | None
    ) -> "WebSocketEvent":
        return cls(
            type="proactive_queue",
            payload={
                "count": count,
                "top_item": top_item.to_dict() if top_item else None,
            },
        )

    @classmethod
    def approval_request(cls, request: ApprovalRequestPayload) -> "WebSocketEvent":
        return cls(type="approval_request", payload=request.to_dict())

    @classmethod
    def message(cls, message: ChatMessage) -> "WebSocketEvent":
        return cls(type="message", payload=message.to_dict())

    @classmethod
    def approval_resolved(cls, event_id: str, approved: bool) -> "WebSocketEvent":
        return cls(
            type="approval_resolved",
            payload={"event_id": event_id, "approved": approved},
        )

    @classmethod
    def proactive_surfaced(cls, item: ProactiveItem) -> "WebSocketEvent":
        return cls(type="proactive_surfaced", payload=item.to_dict())

    @classmethod
    def component_health(cls, components: list[ComponentHealthEntry]) -> "WebSocketEvent":
        return cls(
            type="component_health",
            payload={"components": [item.to_dict() for item in components]},
        )

    @classmethod
    def failure_prompt(cls, request: FailurePromptPayload) -> "WebSocketEvent":
        return cls(type="failure_prompt", payload=request.to_dict())

    @classmethod
    def failure_resolved(cls, event_id: str, action: str) -> "WebSocketEvent":
        return cls(
            type="failure_resolved",
            payload={"event_id": event_id, "action": action},
        )

    @classmethod
    def lock_state(cls, locked: bool) -> "WebSocketEvent":
        return cls(type="lock_state", payload={"locked": locked})

    @classmethod
    def anomaly_alert(cls, destination: str, detail: str, timestamp: str) -> "WebSocketEvent":
        return cls(
            type="anomaly_alert",
            payload={"destination": destination, "detail": detail, "timestamp": timestamp},
        )

    @classmethod
    def lm_studio_wait(cls, *, waiting: bool, message: str) -> "WebSocketEvent":
        return cls(
            type="lm_studio_wait",
            payload={"waiting": waiting, "message": message},
        )

    @classmethod
    def seed_prompt(cls, payload: SeedPromptPayload) -> "WebSocketEvent":
        return cls(type="seed_prompt", payload=payload.to_dict())

    @classmethod
    def seed_confirm(cls, payload: SeedConfirmPayload) -> "WebSocketEvent":
        return cls(type="seed_confirm", payload=payload.to_dict())

    @classmethod
    def seed_summary_review(cls, payload: SeedSummaryReviewPayload) -> "WebSocketEvent":
        return cls(type="seed_summary_review", payload=payload.to_dict())

    @classmethod
    def seed_mode(cls, payload: SeedModePayload) -> "WebSocketEvent":
        return cls(type="seed_mode", payload=payload.to_dict())

    @classmethod
    def config_notify(cls, message: str) -> "WebSocketEvent":
        return cls(type="config_notify", payload={"message": message})

    @classmethod
    def status_snapshot(
        cls,
        *,
        pipeline_step: PipelineStep,
        voice_state: VoiceState,
        mcp_servers: list[McpServerStatus],
        proactive_count: int,
        proactive_top: ProactiveItem | None,
        profile_name: str,
        locked: bool = False,
        component_health: list[ComponentHealthEntry] | None = None,
        lm_studio_waiting: bool = False,
        lm_studio_message: str = "",
    ) -> "WebSocketEvent":
        return cls(
            type="status_snapshot",
            payload={
                "pipeline_step": pipeline_step.value,
                "pipeline_label": pipeline_step.label(),
                "voice_state": voice_state.value,
                "mcp_servers": [server.to_dict() for server in mcp_servers],
                "proactive_count": proactive_count,
                "proactive_top": proactive_top.to_dict() if proactive_top else None,
                "profile_name": profile_name,
                "locked": locked,
                "component_health": [
                    item.to_dict() for item in (component_health or [])
                ],
                "lm_studio_waiting": lm_studio_waiting,
                "lm_studio_message": lm_studio_message,
            },
        )
