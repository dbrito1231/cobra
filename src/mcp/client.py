"""HTTP client for MCP server endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from config.models import McpServerEntry, SUPPORTED_MCP_PROTOCOL


class McpClient:
    """Minimal HTTP MCP client with config fallback for capabilities."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def ping(self, server: McpServerEntry) -> tuple[bool, str]:
        try:
            response = httpx.get(
                f"{server.endpoint.rstrip('/')}/health",
                timeout=self.timeout_seconds,
            )
            if response.status_code == 200:
                return True, "reachable"
            return False, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    def fetch_capabilities(
        self,
        server: McpServerEntry,
    ) -> tuple[list[str], str, str | None]:
        """Return capabilities, protocol version, and optional error."""

        try:
            response = httpx.get(
                f"{server.endpoint.rstrip('/')}/capabilities",
                timeout=self.timeout_seconds,
            )
            if response.status_code != 200:
                return list(server.capabilities), SUPPORTED_MCP_PROTOCOL, None
            payload = response.json()
            capabilities = payload.get("capabilities") or server.capabilities
            protocol = str(payload.get("protocol_version", SUPPORTED_MCP_PROTOCOL))
            return list(capabilities), protocol, None
        except Exception:
            return list(server.capabilities), SUPPORTED_MCP_PROTOCOL, None

    def invoke(
        self,
        server: McpServerEntry,
        capability: str,
        sanitized_query: str,
    ) -> tuple[bool, Any, str | None]:
        try:
            response = httpx.post(
                f"{server.endpoint.rstrip('/')}/invoke",
                json={"capability": capability, "query": sanitized_query},
                timeout=self.timeout_seconds,
            )
            if response.status_code >= 400:
                return False, None, f"HTTP {response.status_code}"
            return True, response.json(), None
        except Exception as exc:
            return False, None, str(exc)
