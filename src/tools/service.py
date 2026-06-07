"""Tools component service — lifecycle wrapper for the execution spine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Union

from config.reader import ConfigReader
from tools import (
    execute_chain,
    execute_tool,
    pending_approvals,
    pending_failures,
    prune_expired_approvals,
    prune_expired_failures,
    resolve_approval,
    resolve_failure,
)
from tools.config import (
    ToolsConfig,
    configure_sandbox_default,
    reset_session_sandbox,
    set_session_sandbox_override,
)
from tools.models import ApprovalEvent, FailureEvent, ToolCall, ToolResult
from tools.privacy import configure_paths, sanitize_tool_call
from tools.registry import TOOL_CATALOG

ApprovalCallback = Callable[[ApprovalEvent], Union[Awaitable[None], None]]


class HealthStatus:
    def __init__(self, *, healthy: bool, message: str = "ok", degraded: bool = False) -> None:
        self.healthy = healthy
        self.message = message
        self.degraded = degraded


class ToolsService:
    """Top-level Tools component initialized in Orchestrator Phase 3."""

    def __init__(
        self,
        config_reader: ConfigReader,
        *,
        audit_outbound: Callable[..., None] | None = None,
        on_approval_required: ApprovalCallback | None = None,
    ) -> None:
        legacy = self._reader_to_legacy(config_reader)
        self.config = ToolsConfig.from_config_dict(legacy)
        self._audit_outbound = audit_outbound
        self._on_approval_required = on_approval_required
        self._initialized = False

    def initialize(self) -> None:
        configure_paths(wiki_dir=self.config.wiki_dir, logs_dir=self.config.logs_dir)
        configure_sandbox_default(self.config.sandbox_default)
        reset_session_sandbox()
        self.config.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)
        prune_expired_approvals()
        prune_expired_failures()
        self._initialized = True

    def shutdown(self) -> None:
        prune_expired_approvals()
        prune_expired_failures()
        self._initialized = False

    def health(self) -> HealthStatus:
        if not self._initialized:
            return HealthStatus(healthy=False, message="not initialized")
        return HealthStatus(
            healthy=True,
            message=f"{len(TOOL_CATALOG)} tools registered",
        )

    def set_session_sandbox(self, enabled: bool | None) -> None:
        """Per-session sandbox override (sandboxing.md)."""

        self.config.session_sandbox = enabled
        set_session_sandbox_override(enabled)

    async def execute_tool(
        self,
        call: ToolCall,
    ) -> ToolResult | ApprovalEvent | FailureEvent:
        """Primary contract — execute a tool under the approval model."""

        sanitized = sanitize_tool_call(call)
        from tools.config import sandbox_enabled_for_call

        if not self.config.sandbox_enabled:
            sanitized = ToolCall(
                tool_name=sanitized.tool_name,
                params={**sanitized.params, "sandboxed": False},
                sandboxed=False,
                chain_id=sanitized.chain_id,
            )
        elif sandbox_enabled_for_call(sanitized):
            sanitized = ToolCall(
                tool_name=sanitized.tool_name,
                params={**sanitized.params, "sandboxed": True},
                sandboxed=True,
                chain_id=sanitized.chain_id,
            )
        else:
            sanitized = ToolCall(
                tool_name=sanitized.tool_name,
                params={**sanitized.params, "sandboxed": False},
                sandboxed=False,
                chain_id=sanitized.chain_id,
            )

        outcome = await execute_tool(sanitized)
        self._audit_outbound_tool(sanitized, outcome)
        return outcome

    async def execute_chain(self, calls: list[ToolCall]):
        return await execute_chain(calls)

    async def resolve_approval(self, event_id: str, approved: bool) -> ToolResult | ApprovalEvent | FailureEvent:
        return await resolve_approval(event_id, approved)

    async def resolve_failure(
        self,
        event_id: str,
        *,
        continue_chain: bool = False,
    ) -> ToolResult | ApprovalEvent | FailureEvent:
        return await resolve_failure(event_id, continue_chain=continue_chain)

    def pending_approval_ids(self) -> list[str]:
        return list(pending_approvals().keys())

    def pending_failure_ids(self) -> list[str]:
        return list(pending_failures().keys())

    def _audit_outbound_tool(
        self,
        call: ToolCall,
        outcome: ToolResult | ApprovalEvent | FailureEvent,
    ) -> None:
        if self._audit_outbound is None:
            return
        if call.tool_name not in {"web_search", "communication"}:
            return
        query = str(call.params.get("query") or call.params.get("topic") or "")
        if not query:
            return
        if isinstance(outcome, ApprovalEvent):
            return

        from security.models import ApprovalStatus, RequestOutcome

        if isinstance(outcome, ToolResult):
            request_outcome = (
                RequestOutcome.SUCCESS if outcome.success else RequestOutcome.FAILURE
            )
        else:
            request_outcome = RequestOutcome.FAILURE

        self._audit_outbound(
            call.tool_name,
            query,
            trigger="pipeline",
            approval_status=ApprovalStatus.AUTO,
            outcome=request_outcome,
        )

    @staticmethod
    def _reader_to_legacy(reader: ConfigReader) -> dict:
        profile = reader.active_profile()
        return {
            "storage": profile.storage.model_dump(),
            "tool_sandbox": profile.tool_sandbox,
        }
