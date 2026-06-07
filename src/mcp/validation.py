"""Startup validation S1–S7."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from config.models import McpServerEntry, SUPPORTED_MCP_PROTOCOL

from mcp.client import McpClient
from mcp.models import RegistryEntry, ServerAvailability
from mcp.registry import LiveRegistry


class StartupValidator:
    """Connect to all configured MCP servers simultaneously."""

    def __init__(self, client: McpClient | None = None) -> None:
        self.client = client or McpClient()

    def validate_all(
        self,
        servers: list[McpServerEntry],
        registry: LiveRegistry,
    ) -> list[tuple[str, bool, str]]:
        results: list[tuple[str, bool, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, len(servers))) as pool:
            futures = {
                pool.submit(self._validate_one, server, registry): server.name
                for server in servers
            }
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def _validate_one(
        self,
        server: McpServerEntry,
        registry: LiveRegistry,
    ) -> tuple[str, bool, str]:
        entry = registry.upsert(server)
        entry.status = ServerAvailability.VALIDATING

        reachable, ping_message = self.client.ping(server)
        if not reachable:
            registry.mark_unavailable(server.name, message=ping_message)
            return server.name, False, ping_message

        capabilities, protocol, _ = self.client.fetch_capabilities(server)
        if not capabilities:
            registry.mark_unavailable(
                server.name,
                message="No capabilities declared",
            )
            return server.name, False, "No capabilities declared"

        if protocol != SUPPORTED_MCP_PROTOCOL:
            registry.mark_unavailable(
                server.name,
                message=f"Incompatible protocol version: {protocol}",
            )
            return (
                server.name,
                False,
                f"Incompatible protocol version: {protocol}",
            )

        registry.mark_available(
            server.name,
            capabilities=capabilities,
            protocol_version=protocol,
        )
        return server.name, True, "available"
