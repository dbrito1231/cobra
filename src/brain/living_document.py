"""Living document updates per specs/seed-document/living-document.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from brain.seed_document import STAGE_SECTIONS

if TYPE_CHECKING:
    from brain.model_layer import ModelLayer
    from brain.seed_document import SeedDocumentManager

HISTORY_FILENAME = "you-history.md"
OBSERVED_SECTION = "Observed Patterns"

_SECTION_NAMES = list(STAGE_SECTIONS.values()) + [OBSERVED_SECTION]


class LivingDocumentManager:
    """LV1–LV5: session-driven updates, reconciliation, version history."""

    def __init__(
        self,
        seed: SeedDocumentManager,
        model: ModelLayer | None,
        wiki_dir: Path,
    ) -> None:
        self.seed = seed
        self.model = model
        self.history_path = wiki_dir / HISTORY_FILENAME

    def update_from_session(self, meta_summary: str) -> list[str]:
        if not meta_summary.strip():
            return []

        touched: list[str] = []
        signals = self._extract_signals(meta_summary)
        for section, update in signals.items():
            if section in self.seed.state.overrides:
                continue
            if section == OBSERVED_SECTION:
                self._append_observed_pattern(update)
                touched.append(section)
                continue
            existing = self.seed.read_section(section)
            if not existing or "(To be filled" in existing:
                continue
            merged = self._reconcile(section, existing, update)
            if merged != existing:
                old = existing
                self.seed.write_section(section, merged)
                self._append_version_history(section, old, merged, "session")
                touched.append(section)
        return touched

    def apply_override(self, section: str, content: str) -> None:
        old = self.seed.read_section(section)
        self.seed.write_section(section, content)
        stamp = datetime.now(timezone.utc).isoformat()
        self.seed.state.overrides[section] = {"content": content, "updated_at": stamp}
        self.seed._save_state()
        self.write_section_with_history(section, content, "override", old_body=old)

    def write_section_with_history(
        self,
        section: str,
        content: str,
        source: str,
        *,
        old_body: str | None = None,
    ) -> None:
        old = old_body if old_body is not None else self.seed.read_section(section)
        self.seed.write_section(section, content)
        self._append_version_history(section, old, content, source)
        self._ensure_history_indexed()

    def _ensure_history_indexed(self) -> None:
        if not self.history_path.exists():
            return
        index_path = self.history_path.parent / "index.md"
        if not index_path.exists():
            return
        content = index_path.read_text(encoding="utf-8")
        if "you-history.md" in content:
            return
        rows = content.rstrip().splitlines()
        rows.append("| you-history.md | You page version history |")
        index_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _extract_signals(self, meta_summary: str) -> dict[str, str]:
        fallback = {OBSERVED_SECTION: f"- Session note: {meta_summary[:120].strip()}"}
        if self.model is None:
            return fallback

        section_list = ", ".join(_SECTION_NAMES)
        prompt = (
            f"Session summary:\n{meta_summary}\n\n"
            f"Extract stable behavioral signals for these wiki sections: {section_list}.\n"
            "Return JSON object mapping section name to a short bullet or sentence. "
            "Only include sections with clear evidence. Include Observed Patterns when useful."
        )
        try:
            result = self.model.complete(
                prompt,
                system="Return only valid JSON object. No markdown fences.",
                max_tokens=400,
                temperature=0.2,
            )
            if result.text.strip() and not result.offline:
                parsed = json.loads(result.text.strip())
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items() if v.strip()}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return fallback

    def _reconcile(self, section: str, existing: str, update: str) -> str:
        if update.strip() in existing:
            return existing
        if self.model is None:
            return f"{existing.rstrip()}\n\n{update.strip()}"

        prompt = (
            f"Section: {section}\n"
            f"Current text:\n{existing}\n\n"
            f"New observation:\n{update}\n\n"
            "If they contradict, newer observation wins. Merge into one concise paragraph. "
            "Return only the merged section body."
        )
        try:
            result = self.model.complete(
                prompt,
                system="Reconcile personality profile sections. Return only merged text.",
                max_tokens=300,
                temperature=0.2,
            )
            if result.text.strip() and not result.offline:
                merged = result.text.strip()
                if merged != existing:
                    self._append_version_history(
                        section,
                        existing,
                        merged,
                        "session",
                        note="contradiction reconciled — newer observation wins",
                    )
                return merged
        except Exception:
            pass
        return f"{existing.rstrip()}\n\n{update.strip()}"

    def _append_observed_pattern(self, bullet: str) -> None:
        existing = self.seed.read_section(OBSERVED_SECTION)
        if bullet.strip() in existing:
            return
        if not existing or "(Auto-populated" in existing:
            body = bullet.strip()
        else:
            body = f"{existing.rstrip()}\n{bullet.strip()}"
        old = existing
        self.seed.write_section(OBSERVED_SECTION, body)
        self._append_version_history(OBSERVED_SECTION, old, body, "session")

    def _append_version_history(
        self,
        section: str,
        old: str,
        new: str,
        source: str,
        *,
        note: str = "",
    ) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"## {stamp}\n- **Section:** {section}\n- **Source:** {source}\n"
        if note:
            header += f"- **Note:** {note}\n"
        entry = (
            f"{header}"
            f"- **Before:** {old[:200].strip() or '(empty)'}\n"
            f"- **After:** {new[:200].strip() or '(empty)'}\n\n"
        )
        if self.history_path.exists():
            existing = self.history_path.read_text(encoding="utf-8")
            content = existing.rstrip() + "\n\n" + entry
        else:
            content = f"# You Page Version History\n\n{entry}"
        self.history_path.write_text(content, encoding="utf-8")

    def read_history(self) -> str:
        if not self.history_path.exists():
            return ""
        return self.history_path.read_text(encoding="utf-8")

    @staticmethod
    def resolve_section_name(raw: str) -> str | None:
        lowered = raw.strip().lower()
        aliases = {
            "communication": "Communication Style",
            "communication style": "Communication Style",
            "decision": "Decision-Making",
            "decision-making": "Decision-Making",
            "decision making": "Decision-Making",
            "values": "Values and Beliefs",
            "values and beliefs": "Values and Beliefs",
            "humor": "Humor and Personality",
            "humor and personality": "Humor and Personality",
            "personality": "Humor and Personality",
            "context": "Context-Specific Behavior",
            "context-specific behavior": "Context-Specific Behavior",
            "context behavior": "Context-Specific Behavior",
            "observed patterns": OBSERVED_SECTION,
            "patterns": OBSERVED_SECTION,
        }
        if lowered in aliases:
            return aliases[lowered]
        for name in _SECTION_NAMES:
            if name.lower() == lowered:
                return name
        return None
