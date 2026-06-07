"""Wiki MCP log L1–L6."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mcp.models import CallOutcome, McpLogEntry


class McpWikiLogger:
    """Append MCP interactions to ~/.cobra/wiki/mcp-log.md."""

    def __init__(self, wiki_dir: Path) -> None:
        self.log_path = Path(wiki_dir).expanduser() / "mcp-log.md"

    def ensure_ready(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("# MCP Log\n\n", encoding="utf-8")

    def log(self, entry: McpLogEntry) -> None:
        self.ensure_ready()
        block = (
            f"\n## {entry.timestamp.isoformat()}\n"
            f"- Server: {entry.server_name} ({entry.endpoint})\n"
            f"- Capability: {entry.capability}\n"
            f"- Query: {entry.sanitized_query}\n"
            f"- Response: {entry.response_summary}\n"
            f"- Outcome: {entry.outcome.value}\n"
            f"- Approval: {entry.approval}\n"
        )
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(block)

    def summarize_response(self, payload) -> str:
        if payload is None:
            return "none"
        text = str(payload)
        return text if len(text) <= 240 else text[:237] + "..."
