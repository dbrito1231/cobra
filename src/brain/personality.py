"""Personality model and mirror per specs/brain/personality-model.md."""

from __future__ import annotations

from brain.memory.wiki import WikiStore
from brain.model_layer import ModelLayer
from brain.models import SharedContext


class PersonalityMirror:
    """Applies You-page voice at pipeline step P5."""

    def __init__(self, wiki: WikiStore, model: ModelLayer) -> None:
        self.wiki = wiki
        self.model = model

    def apply(self, draft: str, context: SharedContext) -> str:
        you_page = self.wiki.read("you")
        if not you_page.strip():
            return draft

        mood_hint = f"Mood: {context.mood}, energy: {context.energy:.1f}."
        completion = self.model.complete(
            f"Rewrite this response in the user's voice.\n\nYou page:\n{you_page[:1500]}\n\n"
            f"{mood_hint}\n\nDraft:\n{draft}",
            system="Keep facts intact. Adjust tone only. Return only the rewritten response.",
            max_tokens=512,
        )
        return completion.text.strip() or draft

    def log_behavior(self, user_text: str, response: str) -> None:
        stamp = self.wiki.read("you").count("## Observed Patterns")
        if stamp == 0:
            return
        snippet = f"- User asked about: {user_text[:80]}; responded concisely."
        content = self.wiki.read("you")
        if "## Observed Patterns" in content:
            parts = content.split("## Observed Patterns", 1)
            updated = parts[0] + "## Observed Patterns\n" + snippet + "\n" + parts[1].lstrip()
            self.wiki.write("you", updated)

    def is_personality_ready(self) -> bool:
        you = self.wiki.read("you")
        return "(To be filled" not in you
