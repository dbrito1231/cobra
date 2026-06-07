"""Live registry R1–R3."""

from __future__ import annotations

from config.models import McpServerEntry

from mcp.models import RegistryEntry, ServerAvailability


class LiveRegistry:
    """Runtime catalog of MCP servers, capabilities, and availability."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def upsert(self, server: McpServerEntry) -> RegistryEntry:
        entry = self._entries.get(server.name) or RegistryEntry(server=server)
        entry.server = server
        self._entries[server.name] = entry
        return entry

    def mark_available(
        self,
        name: str,
        *,
        capabilities: list[str],
        protocol_version: str,
        message: str = "ok",
    ) -> None:
        entry = self._entries[name]
        entry.status = ServerAvailability.AVAILABLE
        entry.declared_capabilities = capabilities
        entry.protocol_version = protocol_version
        entry.message = message

    def mark_unavailable(self, name: str, *, message: str) -> None:
        entry = self._entries[name]
        entry.status = ServerAvailability.UNAVAILABLE
        entry.message = message

    def get(self, name: str) -> RegistryEntry | None:
        return self._entries.get(name)

    def all(self) -> list[RegistryEntry]:
        return list(self._entries.values())

    def available_for_capability(self, capability: str) -> list[RegistryEntry]:
        matches = [
            entry
            for entry in self._entries.values()
            if entry.status == ServerAvailability.AVAILABLE
            and capability in entry.declared_capabilities
        ]
        return sorted(matches, key=lambda item: item.server.priority)

    def status_snapshot(self) -> list[dict[str, str]]:
        return [entry.to_status_dict() for entry in self.all()]
