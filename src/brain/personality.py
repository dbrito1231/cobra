"""Personality model and mirror per specs/brain/personality-model.md."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brain.memory.wiki import WikiStore
from brain.model_layer import ModelLayer
from brain.models import SharedContext

if TYPE_CHECKING:
    from brain.living_document import LivingDocumentManager


class PersonalityMirror:
    """Applies You-page voice at pipeline step P5."""

    def __init__(
        self,
        wiki: WikiStore,
        model: ModelLayer,
        *,
        living_doc: LivingDocumentManager | None = None,
    ) -> None:
        self.wiki = wiki
        self.model = model
        self.living_doc = living_doc

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
        if self.living_doc is None:
            return
        summary = f"User said: {user_text[:120]}. C.O.B.R.A. responded: {response[:120]}."
        self.living_doc.update_from_session(summary)

    def is_personality_ready(self) -> bool:
        you = self.wiki.read("you")
        return "(To be filled" not in you
