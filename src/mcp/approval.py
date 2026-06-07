"""MCP approval model E/F/DENIED."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from mcp.models import McpApprovalRequest


@dataclass
class PendingApproval:
    request: McpApprovalRequest
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class McpApprovalManager:
    """Track pending MCP approvals until user resolves them."""

    def __init__(self, *, ttl_seconds: int = 300) -> None:
        self._pending: dict[str, PendingApproval] = {}
        self.ttl_seconds = ttl_seconds

    def create(self, request: McpApprovalRequest) -> McpApprovalRequest:
        self._pending[request.event_id] = PendingApproval(request=request)
        return request

    def resolve(self, event_id: str, approved: bool) -> McpApprovalRequest | None:
        pending = self._pending.pop(event_id, None)
        if pending is None:
            return None
        return pending.request if approved else None

    def get(self, event_id: str) -> McpApprovalRequest | None:
        pending = self._pending.get(event_id)
        return pending.request if pending else None

    def prune_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)
        expired = [
            event_id
            for event_id, pending in self._pending.items()
            if pending.created_at < cutoff
        ]
        for event_id in expired:
            self._pending.pop(event_id, None)

    def pending_requests(self) -> list[McpApprovalRequest]:
        self.prune_expired()
        return [item.request for item in self._pending.values()]
