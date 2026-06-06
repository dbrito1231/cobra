"""Multi-tool chain state and control."""

from __future__ import annotations

from dataclasses import dataclass, field

from tools.models import ToolCall, ToolResult


@dataclass
class ToolChain:
    """A planned sequence of tool calls from the brain pipeline."""

    chain_id: str
    calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)
    next_index: int = 0

    def has_next(self) -> bool:
        return self.next_index < len(self.calls)

    def peek_next(self) -> ToolCall | None:
        if not self.has_next():
            return None
        return self.calls[self.next_index]

    def advance(self) -> None:
        self.next_index += 1


def should_continue_chain(chain: ToolChain) -> bool:
    """Nodes D/T: determine whether another tool remains in the chain."""

    return chain.has_next()
