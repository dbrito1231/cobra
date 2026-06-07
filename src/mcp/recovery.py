"""Server-down mid-session recovery D1–D5."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from config.models import McpServerEntry

from mcp.client import McpClient
from mcp.registry import LiveRegistry


class ServerRecoveryManager:
    """Silent background retry before marking a server unavailable."""

    def __init__(
        self,
        registry: LiveRegistry,
        client: McpClient | None = None,
        *,
        retry_interval_seconds: float = 5.0,
        max_retries: int = 3,
        on_recovered: Callable[[str], None] | None = None,
        on_unavailable: Callable[[str, str], None] | None = None,
    ) -> None:
        self.registry = registry
        self.client = client or McpClient()
        self.retry_interval_seconds = retry_interval_seconds
        self.max_retries = max_retries
        self._on_recovered = on_recovered
        self._on_unavailable = on_unavailable
        self._paused_tasks: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def handle_failure(self, server: McpServerEntry, capability: str) -> None:
        thread = threading.Thread(
            target=self._retry_loop,
            args=(server, capability),
            name=f"mcp-recovery-{server.name}",
            daemon=True,
        )
        thread.start()

    def paused_tasks(self, server_name: str) -> list[str]:
        with self._lock:
            return list(self._paused_tasks.get(server_name, []))

    def _retry_loop(self, server: McpServerEntry, capability: str) -> None:
        for _ in range(self.max_retries):
            time.sleep(self.retry_interval_seconds)
            ok, message = self.client.ping(server)
            if ok:
                capabilities, protocol, _ = self.client.fetch_capabilities(server)
                self.registry.mark_available(
                    server.name,
                    capabilities=capabilities,
                    protocol_version=protocol,
                    message="recovered",
                )
                if self._on_recovered:
                    self._on_recovered(server.name)
                return

        self.registry.mark_unavailable(server.name, message="retry period expired")
        with self._lock:
            self._paused_tasks.setdefault(server.name, []).append(capability)
        if self._on_unavailable:
            self._on_unavailable(server.name, capability)
