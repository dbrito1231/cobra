"""Conversation session persistence for chat history and search."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from chat_ui.models import ChatMessage


class SessionStore:
    """Stores the active session and archived session logs on disk."""

    def __init__(self, sessions_dir: Path) -> None:
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        self._messages: list[ChatMessage] = []
        self._load_active()

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def messages(self) -> list[ChatMessage]:
        return list(self._messages)

    def _active_path(self) -> Path:
        return self.sessions_dir / f"{self._session_id}.json"

    def _load_active(self) -> None:
        path = self._active_path()
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self._messages = [ChatMessage.from_dict(item) for item in data.get("messages", [])]

    def add_message(self, sender: str, content: str) -> ChatMessage:
        message = ChatMessage(sender=sender, content=content)
        self._messages.append(message)
        self._persist()
        return message

    def get_message(self, message_id: str) -> ChatMessage | None:
        for message in self._messages:
            if message.id == message_id:
                return message
        return None

    def _persist(self) -> None:
        payload = {
            "session_id": self._session_id,
            "started_at": self._session_id.replace("_", "T", 1),
            "messages": [message.to_dict() for message in self._messages],
        }
        self._active_path().write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def iter_all_sessions(self) -> list[dict]:
        sessions: list[dict] = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            sessions.append(
                {
                    "session_id": data.get("session_id", path.stem),
                    "started_at": data.get("started_at", path.stem),
                    "messages": data.get("messages", []),
                }
            )
        return sessions

    def new_session(self) -> str:
        self._session_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        self._messages = []
        return self._session_id

    def load_session(self, session_id: str) -> list[ChatMessage]:
        """Load messages from an archived or active session file."""

        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [ChatMessage.from_dict(item) for item in data.get("messages", [])]

    def switch_session(self, session_id: str) -> list[ChatMessage]:
        """Switch the active session to a stored session and return its messages."""

        messages = self.load_session(session_id)
        if not messages and session_id != self._session_id:
            path = self.sessions_dir / f"{session_id}.json"
            if not path.exists():
                return []
        self._session_id = session_id
        self._messages = messages
        return list(self._messages)
