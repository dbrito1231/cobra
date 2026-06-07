"""Manual MCP server registration from config."""

from __future__ import annotations

from config.models import McpServerEntry


def discover_servers(entries: list[McpServerEntry]) -> list[McpServerEntry]:
    """Load manually configured servers only — no auto-discovery."""

    return [entry for entry in entries if entry.enabled]
