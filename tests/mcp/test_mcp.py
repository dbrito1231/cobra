"""Tests for the MCP Server Layer component."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from config.models import McpServerEntry
from mcp.client import McpClient
from mcp.discovery import discover_servers
from mcp.models import ServerAvailability
from mcp.privacy import sanitize_query
from mcp.registry import LiveRegistry
from mcp.routing import CapabilityRouter
from mcp.service import McpService
from mcp.validation import StartupValidator


@pytest.fixture
def web_server() -> McpServerEntry:
    return McpServerEntry(
        name="Web Search MCP",
        endpoint="http://127.0.0.1:3000",
        capabilities=["web_search"],
        enabled=True,
    )


class TestDiscovery:
    def test_only_enabled_servers(self, web_server: McpServerEntry) -> None:
        disabled = McpServerEntry(
            name="Disabled",
            endpoint="http://127.0.0.1:3002",
            capabilities=["calendar_read"],
            enabled=False,
        )
        assert discover_servers([web_server, disabled]) == [web_server]


class TestRouting:
    def test_routes_first_available(self, web_server: McpServerEntry) -> None:
        registry = LiveRegistry()
        registry.upsert(web_server)
        registry.mark_available(
            web_server.name,
            capabilities=["web_search"],
            protocol_version="1.0",
        )
        router = CapabilityRouter(registry)
        entry = router.route("web_search")
        assert entry is not None
        assert entry.server.name == web_server.name


class TestPrivacy:
    def test_sanitize_query(self) -> None:
        assert "[email]" in sanitize_query("Contact user@example.com about topic")


class TestStartupValidator:
    def test_marks_server_available(self, web_server: McpServerEntry, monkeypatch) -> None:
        client = McpClient()
        monkeypatch.setattr(
            client,
            "ping",
            lambda server: (True, "ok"),
        )
        monkeypatch.setattr(
            client,
            "fetch_capabilities",
            lambda server: (["web_search"], "1.0", None),
        )
        registry = LiveRegistry()
        validator = StartupValidator(client)
        results = validator.validate_all([web_server], registry)
        assert results[0][1] is True
        assert registry.get(web_server.name).status == ServerAvailability.AVAILABLE


class TestMcpService:
    @pytest.mark.asyncio
    async def test_call_mcp_unavailable_capability(self, tmp_path: Path) -> None:
        service = McpService(wiki_dir=tmp_path)
        service.initialize([])
        result = await service.call_mcp("web_search", "topic only")
        assert not result.success
        assert result.outcome.value == "unavailable"

    @pytest.mark.asyncio
    async def test_call_mcp_with_auto_approve(
        self,
        web_server: McpServerEntry,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        service = McpService(wiki_dir=tmp_path, audit_outbound=lambda *args, **kwargs: None)
        client = service.client
        monkeypatch.setattr(client, "ping", lambda server: (True, "ok"))
        monkeypatch.setattr(
            client,
            "fetch_capabilities",
            lambda server: (["web_search"], "1.0", None),
        )
        monkeypatch.setattr(
            client,
            "invoke",
            lambda server, capability, query: (True, {"result": "ok"}, None),
        )
        service.initialize([web_server])
        result = await service.call_mcp("web_search", "sanitized topic", auto_approve=True)
        assert result.success
        assert result.output == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_call_mcp_blocking_approval_granted(
        self,
        web_server: McpServerEntry,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        from orchestrator.approval_wait import ApprovalWaitRegistry

        waits = ApprovalWaitRegistry()
        pending: dict[str, str] = {}

        async def approval_prompt(request):
            pending["event_id"] = request.event_id
            future = waits.register(request.event_id)
            return await future

        service = McpService(
            wiki_dir=tmp_path,
            approval_prompt=approval_prompt,
            audit_outbound=lambda *args, **kwargs: None,
        )
        client = service.client
        monkeypatch.setattr(client, "ping", lambda server: (True, "ok"))
        monkeypatch.setattr(
            client,
            "fetch_capabilities",
            lambda server: (["web_search"], "1.0", None),
        )
        monkeypatch.setattr(
            client,
            "invoke",
            lambda server, capability, query: (True, {"result": "approved"}, None),
        )
        service.initialize([web_server])

        call_task = asyncio.create_task(service.call_mcp("web_search", "topic only"))
        await asyncio.sleep(0.01)
        assert "event_id" in pending
        assert waits.resolve(pending["event_id"], True)

        result = await call_task
        assert result.success
        assert result.output == {"result": "approved"}

    @pytest.mark.asyncio
    async def test_call_mcp_blocking_approval_denied(
        self,
        web_server: McpServerEntry,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        from orchestrator.approval_wait import ApprovalWaitRegistry

        waits = ApprovalWaitRegistry()
        pending: dict[str, str] = {}

        async def approval_prompt(request):
            pending["event_id"] = request.event_id
            return await waits.register(request.event_id)

        service = McpService(
            wiki_dir=tmp_path,
            approval_prompt=approval_prompt,
            audit_outbound=lambda *args, **kwargs: None,
        )
        client = service.client
        monkeypatch.setattr(client, "ping", lambda server: (True, "ok"))
        monkeypatch.setattr(
            client,
            "fetch_capabilities",
            lambda server: (["web_search"], "1.0", None),
        )
        monkeypatch.setattr(
            client,
            "invoke",
            lambda server, capability, query: (True, {"result": "should-not-run"}, None),
        )
        service.initialize([web_server])

        call_task = asyncio.create_task(service.call_mcp("web_search", "topic only"))
        await asyncio.sleep(0.01)
        waits.resolve(pending["event_id"], False)

        result = await call_task
        assert not result.success
        assert result.outcome.value == "denied"

    @pytest.mark.asyncio
    async def test_resolve_approval_re_executes_deferred_call(
        self,
        web_server: McpServerEntry,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        service = McpService(wiki_dir=tmp_path, audit_outbound=lambda *args, **kwargs: None)
        client = service.client
        monkeypatch.setattr(client, "ping", lambda server: (True, "ok"))
        monkeypatch.setattr(
            client,
            "fetch_capabilities",
            lambda server: (["web_search"], "1.0", None),
        )
        monkeypatch.setattr(
            client,
            "invoke",
            lambda server, capability, query: (True, {"result": "deferred"}, None),
        )
        service.initialize([web_server])

        pending = await service.call_mcp("web_search", "topic only")
        assert not pending.success
        assert pending.error == "Approval required"

        requests = service.approvals.pending_requests()
        assert len(requests) == 1

        result = await service.resolve_approval(requests[0].event_id, True)
        assert result is not None
        assert result.success
        assert result.output == {"result": "deferred"}

