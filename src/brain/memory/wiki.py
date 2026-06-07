"""Wiki file layout W1–W8 per specs/brain/memory-architecture.md."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

WIKI_PAGES = {
    "you": "you.md",
    "preferences": "preferences.md",
    "verified_facts": "verified_facts.md",
    "topics": "topics.md",
    "decisions": "decisions.md",
    "non_findings": "non_findings.md",
    "index": "index.md",
    "log": "log.md",
}

DEFAULT_YOU = """# You
*Last updated: {date}*

## Communication Style
(To be filled from seed document interview)

## Decision-Making
(To be filled from seed document interview)

## Values and Beliefs
(To be filled from seed document interview)

## Humor and Personality
(To be filled from seed document interview)

## Context-Specific Behavior
(Added in later stages)

## Observed Patterns
(Auto-populated from behavioral logging)
"""

DEFAULT_INDEX = """# Wiki Index

| Page | Summary |
|------|---------|
| you.md | Personality and communication style |
| preferences.md | Timestamped preference evolution |
| verified_facts.md | Permanently verified facts |
| topics.md | Topic notes and analyses |
| decisions.md | Recorded decisions |
| non_findings.md | Unverified topics (30-day TTL) |
"""


class WikiStore:
    """Manages local markdown wiki pages."""

    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        for name, filename in WIKI_PAGES.items():
            path = self.wiki_dir / filename
            if path.exists():
                continue
            if name == "you":
                path.write_text(
                    DEFAULT_YOU.format(date=datetime.now(timezone.utc).date()),
                    encoding="utf-8",
                )
            elif name == "index":
                path.write_text(DEFAULT_INDEX, encoding="utf-8")
            else:
                path.write_text(f"# {name.replace('_', ' ').title()}\n\n", encoding="utf-8")

    def read(self, page: str) -> str:
        filename = WIKI_PAGES.get(page, page if page.endswith(".md") else f"{page}.md")
        path = self.wiki_dir / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write(self, page: str, content: str) -> None:
        filename = WIKI_PAGES.get(page, page if page.endswith(".md") else f"{page}.md")
        path = self.wiki_dir / filename
        path.write_text(content, encoding="utf-8")

    def append(self, page: str, content: str) -> None:
        existing = self.read(page)
        self.write(page, existing.rstrip() + "\n\n" + content.strip() + "\n")

    def append_log(self, operation: str, detail: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        self.append("log", f"- `{stamp}` **{operation}**: {detail}")

    def list_pages(self) -> list[str]:
        return sorted(path.name for path in self.wiki_dir.glob("*.md"))

    def update_index(self) -> None:
        rows = ["# Wiki Index", "", "| Page | Summary |", "|------|---------|"]
        for filename in self.list_pages():
            if filename == "index.md":
                continue
            first_line = (self.wiki_dir / filename).read_text(encoding="utf-8").splitlines()
            summary = first_line[0].lstrip("# ").strip() if first_line else filename
            rows.append(f"| {filename} | {summary} |")
        self.write("index", "\n".join(rows) + "\n")
