"""Capability routing RT1–RT5."""

from __future__ import annotations

from mcp.models import RegistryEntry
from mcp.registry import LiveRegistry


class CapabilityRouter:
    """Select first available server declaring a capability."""

    def __init__(self, registry: LiveRegistry) -> None:
        self.registry = registry

    def route(self, capability: str) -> RegistryEntry | None:
        matches = self.registry.available_for_capability(capability)
        return matches[0] if matches else None
