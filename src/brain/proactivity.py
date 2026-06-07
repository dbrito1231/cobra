"""Proactivity engine per specs/brain/proactivity-engine.md."""

from __future__ import annotations

from brain.models import ProactiveObservation

SEED_MV3_ID = "seed-mv3"
SEED_MV3_PREVIEW = (
    "Your personality model is active. Complete the optional profile interview "
    "when you have time — say \"continue personality interview\" to start."
)
PE2_REFRESH_ID_PREFIX = "pe2-refresh-"


class ProactivityEngine:
    """Event-driven queue — dormant until conversation complete."""

    def __init__(self) -> None:
        self._session_buffer: list[tuple[str, str]] = []
        self._queue: list[ProactiveObservation] = []
        self._conversation_complete = False
        self._silence = False

    def record_exchange(self, user_text: str, response: str) -> None:
        self._session_buffer.append((user_text, response))
        self._detect_patterns()

    def mark_conversation_complete(self) -> None:
        self._conversation_complete = True

    def mark_silence(self) -> None:
        self._silence = True

    def clear_session_buffer(self) -> None:
        self._session_buffer.clear()
        self._conversation_complete = False
        self._silence = False

    def surface_next(self, *, user_asked: bool = False) -> ProactiveObservation | None:
        if not self._queue:
            return None
        if user_asked:
            return self._queue.pop(0)
        if self._conversation_complete and self._silence:
            return self._queue.pop(0)
        return None

    @property
    def queue_count(self) -> int:
        return len(self._queue)

    @property
    def top_item(self) -> ProactiveObservation | None:
        return self._queue[0] if self._queue else None

    def _detect_patterns(self) -> None:
        if len(self._session_buffer) < 3:
            return
        recent_topics: dict[str, int] = {}
        for user_text, _ in self._session_buffer[-6:]:
            for word in user_text.lower().split():
                if len(word) < 4:
                    continue
                recent_topics[word] = recent_topics.get(word, 0) + 1
        for topic, count in recent_topics.items():
            if count >= 3:
                preview = f"You've asked about '{topic}' several times this session."
                if any(item.preview == preview for item in self._queue):
                    continue
                self._queue.append(
                    ProactiveObservation(
                        preview=preview,
                        priority=count,
                        trigger="pattern",
                    )
                )
                self._queue.sort(key=lambda item: item.priority, reverse=True)

    def enqueue_seed_completion(self) -> None:
        if any(item.id == SEED_MV3_ID for item in self._queue):
            return
        self._queue.insert(
            0,
            ProactiveObservation(
                id=SEED_MV3_ID,
                preview=SEED_MV3_PREVIEW,
                priority=10,
                trigger="seed",
            ),
        )

    def enqueue_pe2_refresh(self, section: str) -> None:
        item_id = f"{PE2_REFRESH_ID_PREFIX}{section.lower().replace(' ', '-')}"
        if any(item.id == item_id for item in self._queue):
            return
        preview = (
            f"It's a good time to refresh **{section}**. "
            f'Say "Refresh {section}" to start a follow-up interview.'
        )
        self._queue.insert(
            0,
            ProactiveObservation(
                id=item_id,
                preview=preview,
                priority=8,
                trigger="pe2",
            ),
        )
