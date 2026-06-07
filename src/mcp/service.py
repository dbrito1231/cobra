"""MCP Server Layer service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union

from config.models import McpServerEntry

from mcp.approval import McpApprovalManager
from mcp.client import McpClient
from mcp.discovery import discover_servers
from mcp.executor import McpExecutor
from mcp.logging import McpWikiLogger
from mcp.models import HealthStatus, McpApprovalRequest, McpCallResult
from mcp.recovery import ServerRecoveryManager
from mcp.registry import LiveRegistry
from mcp.routing import CapabilityRouter
from mcp.validation import StartupValidator

ApprovalPrompt = Callable[
    [McpApprovalRequest],
    Union[Awaitable[bool], bool],
]


class McpService:
    """Top-level MCP component initialized in Orchestrator Phase 2."""

    def __init__(
        self,
        *,
        wiki_dir: Path | None = None,
        approval_prompt: ApprovalPrompt | None = None,
        audit_outbound: Callable[..., None] | None = None,
        on_validation_failure: Callable[[list[tuple[str, bool, str]]], None] | None = None,
    ) -> None:
        self.registry = LiveRegistry()
        self.client = McpClient()
        self.approvals = McpApprovalManager()
        self.router = CapabilityRouter(self.registry)
        self.recovery = ServerRecoveryManager(self.registry, self.client)
        self.logger = McpWikiLogger(wiki_dir or Path.home() / ".cobra" / "wiki")
        self.executor = McpExecutor(
            self.router,
            self.client,
            self.approvals,
            self.logger,
            self.recovery,
            approval_prompt=approval_prompt,
            audit_outbound=audit_outbound,
        )
        self._validator = StartupValidator(self.client)
        self._on_validation_failure = on_validation_failure
        self._initialized = False
        self._validation_failures: list[tuple[str, bool, str]] = []

    def initialize(self, servers: list[McpServerEntry]) -> list[tuple[str, bool, str]]:
        """Phase 2 MCP init — connect and validate all configured servers."""

        enabled = discover_servers(servers)
        for server in enabled:
            self.registry.upsert(server)
        results = self._validator.validate_all(enabled, self.registry)
        self._validation_failures = [item for item in results if not item[1]]
        if self._validation_failures and self._on_validation_failure:
            self._on_validation_failure(self._validation_failures)
        self._initialized = True
        return results

    def reload_servers(self, servers: list[McpServerEntry]) -> list[tuple[str, bool, str]]:
        return self.initialize(servers)

    async def call_mcp(
        self,
        capability: str,
        sanitized_query: str,
        *,
        trigger: str = "pipeline",
        auto_approve: bool = False,
    ) -> McpCallResult:
        return await self.executor.call_mcp(
            capability,
            sanitized_query,
            trigger=trigger,
            auto_approve=auto_approve,
        )

    async def resolve_approval(self, event_id: str, approved: bool) -> McpCallResult | None:
        return await self.executor.resolve_approval(event_id, approved)

    def status_snapshot(self) -> list[dict[str, str]]:
        return self.registry.status_snapshot()

    def validation_failures(self) -> list[tuple[str, bool, str]]:
        return list(self._validation_failures)

    def shutdown(self) -> None:
        self._initialized = False

    def health(self) -> HealthStatus:
        if not self._initialized:
            return HealthStatus(healthy=False, message="not initialized")
        available = any(
            entry.status.value == "available" for entry in self.registry.all()
        )
        if not self.registry.all():
            return HealthStatus(healthy=True, message="no MCP servers configured")
        if available:
            return HealthStatus(healthy=True)
        return HealthStatus(
            healthy=True,
            message="all configured MCP servers unavailable",
            degraded=True,
        )
