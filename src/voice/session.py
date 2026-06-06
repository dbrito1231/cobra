"""Voice session lifecycle LC1–LC3."""

from __future__ import annotations

from voice.models import SessionState


class SessionLifecycle:
    """Tracks passive → active → responding transitions."""

    def __init__(self) -> None:
        self.state = SessionState.PASSIVE

    def on_wake_word(self) -> None:
        self.state = SessionState.ACTIVE

    def on_user_speech(self) -> None:
        if self.state in {SessionState.ACTIVE, SessionState.RESPONDING}:
            self.state = SessionState.RESPONDING

    def on_response_complete(self) -> None:
        if self.state == SessionState.RESPONDING:
            self.state = SessionState.ACTIVE

    def on_session_end(self) -> None:
        self.state = SessionState.PASSIVE

    @property
    def is_passive(self) -> bool:
        return self.state == SessionState.PASSIVE

    @property
    def is_active(self) -> bool:
        return self.state in {SessionState.ACTIVE, SessionState.RESPONDING}
