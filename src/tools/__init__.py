"""C.O.B.R.A. tools component public API."""

from tools.chaining import ToolChain
from tools.config import ToolsConfig
from tools.executor import (
    execute_chain,
    execute_tool,
    pending_approvals,
    pending_failures,
    prune_expired_approvals,
    prune_expired_failures,
    resolve_approval,
    resolve_failure,
)
from tools.models import ActionType, ApprovalEvent, FailureEvent, ToolCall, ToolResult
from tools.service import ToolsService

__all__ = [
    "ActionType",
    "ApprovalEvent",
    "FailureEvent",
    "ToolCall",
    "ToolChain",
    "ToolResult",
    "ToolsConfig",
    "ToolsService",
    "execute_chain",
    "execute_tool",
    "pending_approvals",
    "pending_failures",
    "prune_expired_approvals",
    "prune_expired_failures",
    "resolve_approval",
    "resolve_failure",
]
