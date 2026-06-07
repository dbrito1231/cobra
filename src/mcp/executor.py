"""Runtime MCP execution B–J."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Union

from mcp.approval import McpApprovalManager
from mcp.client import McpClient
from mcp.logging import McpWikiLogger
from mcp.models import CallOutcome, McpApprovalRequest, McpCallResult, McpLogEntry
from mcp.privacy import sanitize_query
from mcp.recovery import ServerRecoveryManager
from mcp.routing import CapabilityRouter


ApprovalPrompt = Callable[
    [McpApprovalRequest],
    Union[Awaitable[bool], bool],
]


class McpExecutor:
    """Route, approve, invoke, log, and return MCP results."""

    def __init__(
        self,
        router: CapabilityRouter,
        client: McpClient,
        approvals: McpApprovalManager,
        logger: McpWikiLogger,
        recovery: ServerRecoveryManager,
        *,
        approval_prompt: ApprovalPrompt | None = None,
        audit_outbound: Callable[..., None] | None = None,
    ) -> None:
        self.router = router
        self.client = client
        self.approvals = approvals
        self.logger = logger
        self.recovery = recovery
        self._approval_prompt = approval_prompt
        self._audit_outbound = audit_outbound

    async def call_mcp(
        self,
        capability: str,
        sanitized_query: str,
        *,
        trigger: str = "pipeline",
        auto_approve: bool = False,
    ) -> McpCallResult:
        query = sanitize_query(sanitized_query)
        entry = self.router.route(capability)
        if entry is None:
            result = McpCallResult(
                success=False,
                capability=capability,
                server_name="",
                outcome=CallOutcome.UNAVAILABLE,
                error=f"No available MCP server for capability '{capability}'",
                approval_granted=False,
            )
            self._write_log(entry=None, capability=capability, query=query, result=result, approval="n/a")
            return result

        server = entry.server
        request = McpApprovalRequest.create(
            server.name,
            capability,
            query,
        )
        approved = auto_approve
        if not approved:
            if self._approval_prompt is None:
                self.approvals.create(request)
                return McpCallResult(
                    success=False,
                    capability=capability,
                    server_name=server.name,
                    outcome=CallOutcome.DENIED,
                    error="Approval required",
                    approval_granted=False,
                )
            prompt_result = self._approval_prompt(request)
            approved = await prompt_result if hasattr(prompt_result, "__await__") else prompt_result

        if not approved:
            denied = McpCallResult(
                success=False,
                capability=capability,
                server_name=server.name,
                outcome=CallOutcome.DENIED,
                error="User denied MCP call",
                approval_granted=False,
            )
            self._audit(server.endpoint, query, trigger, denied)
            self._write_log(entry, capability, query, denied, approval="denied")
            return denied

        return self._invoke(entry, capability, query, trigger=trigger)

    async def resolve_approval(self, event_id: str, approved: bool) -> McpCallResult | None:
        """Resume a deferred MCP call after the user approves or denies."""

        request = self.approvals.resolve(event_id, approved)
        if request is None:
            return None

        entry = self.router.route(request.capability)
        if entry is None:
            result = McpCallResult(
                success=False,
                capability=request.capability,
                server_name=request.server_name,
                outcome=CallOutcome.UNAVAILABLE,
                error=f"No available MCP server for capability '{request.capability}'",
                approval_granted=approved,
            )
            self._write_log(
                entry=None,
                capability=request.capability,
                query=request.sanitized_query,
                result=result,
                approval="denied" if not approved else "n/a",
            )
            return result

        if not approved:
            denied = McpCallResult(
                success=False,
                capability=request.capability,
                server_name=request.server_name,
                outcome=CallOutcome.DENIED,
                error="User denied MCP call",
                approval_granted=False,
            )
            self._audit(entry.server.endpoint, request.sanitized_query, "approval", denied)
            self._write_log(entry, request.capability, request.sanitized_query, denied, approval="denied")
            return denied

        return self._invoke(
            entry,
            request.capability,
            request.sanitized_query,
            trigger="approval",
        )

    def _invoke(
        self,
        entry,
        capability: str,
        query: str,
        *,
        trigger: str,
    ) -> McpCallResult:
        server = entry.server
        ok, payload, error = self.client.invoke(server, capability, query)
        if not ok:
            self.recovery.handle_failure(server, capability)
            failed = McpCallResult(
                success=False,
                capability=capability,
                server_name=server.name,
                outcome=CallOutcome.FAILURE,
                error=error or "MCP call failed",
            )
            self._audit(server.endpoint, query, trigger, failed)
            self._write_log(entry, capability, query, failed, approval="granted")
            return failed

        success = McpCallResult(
            success=True,
            capability=capability,
            server_name=server.name,
            output=payload,
            outcome=CallOutcome.SUCCESS,
        )
        self._audit(server.endpoint, query, trigger, success)
        self._write_log(entry, capability, query, success, approval="granted")
        return success

    def _audit(self, destination: str, query: str, trigger: str, result: McpCallResult) -> None:
        if self._audit_outbound is None:
            return
        from security.models import ApprovalStatus, RequestOutcome

        outcome = RequestOutcome.SUCCESS if result.success else RequestOutcome.FAILURE
        if result.outcome == CallOutcome.DENIED:
            outcome = RequestOutcome.BLOCKED
        self._audit_outbound(
            destination,
            query,
            trigger=trigger,
            approval_status=ApprovalStatus.APPROVED if result.approval_granted else ApprovalStatus.DENIED,
            outcome=outcome,
        )

    def _write_log(
        self,
        entry,
        capability: str,
        query: str,
        result: McpCallResult,
        *,
        approval: str,
    ) -> None:
        endpoint = entry.server.endpoint if entry else "n/a"
        name = result.server_name or "n/a"
        self.logger.log(
            McpLogEntry(
                server_name=name,
                endpoint=endpoint,
                capability=capability,
                sanitized_query=query,
                response_summary=self.logger.summarize_response(result.output),
                outcome=result.outcome,
                approval=approval,
            )
        )
