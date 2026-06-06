"""Read-only wiki file access for the browser panel."""

from __future__ import annotations

import re
from pathlib import Path


class WikiService:
    """Serves markdown wiki pages from the configured wiki directory."""

    INDEX_FILE = "index.md"

    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir

    def ensure_index(self) -> None:
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.wiki_dir / self.INDEX_FILE
        if index_path.exists():
            return
        index_path.write_text(
            "# C.O.B.R.A. Wiki\n\n"
            "Welcome to your local wiki. Pages will appear here as C.O.B.R.A. "
            "learns and organizes knowledge.\n",
            encoding="utf-8",
        )

    def list_pages(self) -> list[dict[str, str]]:
        self.ensure_index()
        pages: list[dict[str, str]] = []
        for path in sorted(self.wiki_dir.glob("*.md")):
            pages.append(
                {
                    "name": path.stem,
                    "title": self._title_from_file(path),
                    "path": path.name,
                }
            )
        return pages

    def read_page(self, page_name: str) -> dict[str, str]:
        safe_name = self._sanitize_page_name(page_name)
        path = self.wiki_dir / safe_name
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Wiki page not found: {page_name}")
        content = path.read_text(encoding="utf-8")
        return {
            "name": path.stem,
            "title": self._title_from_content(content, path.stem),
            "content": content,
            "path": path.name,
        }

    def read_index(self) -> dict[str, str]:
        return self.read_page(self.INDEX_FILE)

    def _sanitize_page_name(self, page_name: str) -> str:
        name = page_name.strip().replace("\\", "/").lstrip("/")
        if not name.endswith(".md"):
            name = f"{name}.md"
        if ".." in name or name.startswith("/"):
            raise ValueError("Invalid wiki page path")
        return Path(name).name

    def _title_from_file(self, path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return path.stem.replace("-", " ").title()
        return self._title_from_content(content, path.stem)

    def _title_from_content(self, content: str, fallback: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return fallback.replace("-", " ").title()
