"""Local full-text search across conversation sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from chat_ui.session_store import SessionStore


@dataclass(frozen=True)
class SearchResult:
    session_id: str
    session_date: str
    message_id: str
    sender: str
    excerpt: str
    score: int

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "session_date": self.session_date,
            "message_id": self.message_id,
            "sender": self.sender,
            "excerpt": self.excerpt,
        }


class ConversationSearch:
    """On-demand index built from session JSON files."""

    def __init__(self, session_store: SessionStore) -> None:
        self._session_store = session_store

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        terms = [term.lower() for term in re.split(r"\s+", query) if term]
        results: list[SearchResult] = []

        for session in self._session_store.iter_all_sessions():
            session_id = session["session_id"]
            session_date = session.get("started_at", session_id)
            for message in session.get("messages", []):
                content = message.get("content", "")
                lowered = content.lower()
                score = sum(lowered.count(term) for term in terms)
                if score == 0:
                    continue
                excerpt = self._excerpt(content, terms)
                results.append(
                    SearchResult(
                        session_id=session_id,
                        session_date=session_date,
                        message_id=message.get("id", ""),
                        sender=message.get("sender", "unknown"),
                        excerpt=excerpt,
                        score=score,
                    )
                )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def _excerpt(self, content: str, terms: list[str], radius: int = 60) -> str:
        lowered = content.lower()
        index = min(
            (lowered.find(term) for term in terms if term in lowered),
            default=-1,
        )
        if index < 0:
            snippet = content[: radius * 2]
        else:
            start = max(0, index - radius)
            end = min(len(content), index + radius)
            snippet = content[start:end]
        snippet = " ".join(snippet.split())
        if len(content) > len(snippet):
            return f"...{snippet}..."
        return snippet
