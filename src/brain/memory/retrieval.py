"""Memory retrieval — pipeline step P1."""

from __future__ import annotations

from brain.memory.vector import VectorIndex
from brain.memory.wiki import WikiStore
from brain.models import ExecutionPlan, MemoryHit


class MemoryRetriever:
    """Reads index, wiki pages, and vector index for context."""

    def __init__(self, wiki: WikiStore, vector: VectorIndex) -> None:
        self.wiki = wiki
        self.vector = vector

    def retrieve(self, query: str, plan: ExecutionPlan | None = None) -> list[MemoryHit]:
        hits: list[MemoryHit] = []
        index_content = self.wiki.read("index")
        if index_content:
            hits.append(MemoryHit(page="index.md", content=index_content, score=0.1))

        topics = (plan.retrieve_topics if plan else []) or [query]
        for topic in topics:
            for page, content, score in self.vector.search(topic, limit=3):
                hits.append(MemoryHit(page=page, content=content[:2000], score=score))

        for page_name in ("you", "verified_facts", "topics", "preferences"):
            content = self.wiki.read(page_name)
            if content and any(token in content.lower() for token in topic.lower().split() for topic in topics):
                hits.append(MemoryHit(page=f"{page_name}.md", content=content[:2000], score=0.5))

        seen: set[str] = set()
        unique: list[MemoryHit] = []
        for hit in sorted(hits, key=lambda item: item.score, reverse=True):
            if hit.page in seen:
                continue
            seen.add(hit.page)
            unique.append(hit)
        return unique[:8]
