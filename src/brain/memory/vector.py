"""Local vector index — ChromaDB-equivalent semantic search."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


class VectorIndex:
    """Lightweight local vector store using TF-IDF cosine similarity."""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = index_dir / "vectors.json"
        self._documents: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self._index_file.exists():
            return
        try:
            self._documents = json.loads(self._index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._documents = []

    def _save(self) -> None:
        self._index_file.write_text(
            json.dumps(self._documents, indent=2),
            encoding="utf-8",
        )

    def upsert(self, page: str, content: str) -> None:
        self._documents = [doc for doc in self._documents if doc["page"] != page]
        self._documents.append({"page": page, "content": content})
        self._save()

    def remove(self, page: str) -> None:
        self._documents = [doc for doc in self._documents if doc["page"] != page]
        self._save()

    def search(self, query: str, *, limit: int = 5) -> list[tuple[str, str, float]]:
        if not self._documents:
            return []
        query_vec = Counter(_tokenize(query))
        scored: list[tuple[str, str, float]] = []
        for doc in self._documents:
            doc_vec = Counter(_tokenize(doc["content"]))
            score = self._cosine(query_vec, doc_vec)
            if score > 0:
                scored.append((doc["page"], doc["content"], score))
        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:limit]

    @staticmethod
    def _cosine(a: Counter, b: Counter) -> float:
        if not a or not b:
            return 0.0
        dot = sum(a[token] * b.get(token, 0) for token in a)
        norm_a = math.sqrt(sum(value * value for value in a.values()))
        norm_b = math.sqrt(sum(value * value for value in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
