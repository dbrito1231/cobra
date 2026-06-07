"""Wiki ingest, query, and lint per specs/brain/wiki-operations.md."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from brain.memory.vector import VectorIndex
from brain.memory.wiki import WikiStore
from brain.model_layer import ModelLayer

if TYPE_CHECKING:
    from brain.living_document import LivingDocumentManager


class WikiOperations:
    """WO1 ingest, WO2 query, WO3 lint."""

    NON_FINDING_TTL_DAYS = 30

    def __init__(
        self,
        wiki: WikiStore,
        vector: VectorIndex,
        model: ModelLayer,
        *,
        living_doc: LivingDocumentManager | None = None,
    ) -> None:
        self.wiki = wiki
        self.vector = vector
        self.model = model
        self.living_doc = living_doc

    def ingest_session(self, meta_summary: str) -> list[str]:
        """WO1 — update wiki pages from session meta-summary."""

        if not meta_summary.strip():
            return []

        touched: list[str] = []
        stamp = datetime.now(timezone.utc).isoformat()
        topic_entry = f"### Session {stamp}\n{meta_summary.strip()}\n"
        self.wiki.append("topics", topic_entry)
        touched.append("topics.md")
        self.vector.upsert("topics.md", self.wiki.read("topics"))

        completion = self.model.complete(
            f"Extract any stable user preferences from this summary (bullet list):\n{meta_summary}",
            max_tokens=128,
        )
        if completion.text.strip():
            pref_entry = f"### {stamp}\n{completion.text.strip()}\n"
            self.wiki.append("preferences", pref_entry)
            touched.append("preferences.md")
            self.vector.upsert("preferences.md", self.wiki.read("preferences"))

        if self.living_doc is not None:
            living_touched = self.living_doc.update_from_session(meta_summary)
            touched.extend(f"you.md:{section}" for section in living_touched)

        self.wiki.update_index()
        self.wiki.append_log("ingest", f"Updated {', '.join(touched)}")
        return touched

    def query(self, question: str) -> list[tuple[str, str]]:
        """WO2 — index-first query then drill into pages."""

        results: list[tuple[str, str]] = []
        index = self.wiki.read("index")
        if index:
            results.append(("index.md", index))

        for page, content, _score in self.vector.search(question, limit=5):
            results.append((page, content[:2000]))
        return results

    def lint(self) -> list[str]:
        """WO3 — daily health check for contradictions and orphans."""

        issues: list[str] = []
        pages = set(self.wiki.list_pages())
        index = self.wiki.read("index")

        for page in pages:
            if page in {"index.md", "log.md"}:
                continue
            if page not in index:
                issues.append(f"Orphaned page not in index: {page}")

        you = self.wiki.read("you")
        if "(To be filled" in you:
            issues.append("You page incomplete — seed document interview recommended.")

        self._prune_non_findings()
        self.wiki.append_log("lint", f"{len(issues)} issue(s) found")
        return issues

    def store_verified_fact(self, fact: str, sources: list[str]) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        entry = f"### {stamp}\n- {fact}\n- Sources: {', '.join(sources)}\n"
        self.wiki.append("verified_facts", entry)
        self.vector.upsert("verified_facts.md", self.wiki.read("verified_facts"))
        self.wiki.update_index()

    def store_non_finding(self, topic: str) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(days=self.NON_FINDING_TTL_DAYS)
        entry = f"### {topic}\n- Expires: {expiry.date().isoformat()}\n"
        self.wiki.append("non_findings", entry)
        self.vector.upsert("non_findings.md", self.wiki.read("non_findings"))

    def _prune_non_findings(self) -> None:
        content = self.wiki.read("non_findings")
        if not content:
            return
        kept: list[str] = ["# Non Findings", ""]
        today = datetime.now(timezone.utc).date()
        blocks = re.split(r"\n### ", content)
        header = blocks[0]
        if header.strip():
            kept[0] = header.splitlines()[0]
        for block in blocks[1:]:
            expiry_match = re.search(r"Expires:\s*(\d{4}-\d{2}-\d{2})", block)
            if expiry_match:
                expiry = datetime.fromisoformat(expiry_match.group(1)).date()
                if expiry < today:
                    continue
            kept.append("### " + block.rstrip())
        self.wiki.write("non_findings", "\n".join(kept).strip() + "\n")
