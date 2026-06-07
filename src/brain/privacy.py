"""Privacy hard-rule enforcement per specs/brain/privacy.md."""

from __future__ import annotations

import re
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Union

from brain.models import PrivacyDecision
from security.path_redaction import redact_home_paths, MAC_HOME_RE, LINUX_HOME_RE, WINDOWS_HOME_RE, TILDE_HOME_RE

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
HOME_PATH_PATTERNS = (MAC_HOME_RE, LINUX_HOME_RE, WINDOWS_HOME_RE, TILDE_HOME_RE)
PERSONAL_NAME_RE = re.compile(
    r"\b(?:my name is|i am|i'm)\s+[A-Z][a-z]+",
    re.IGNORECASE,
)
FIRST_PERSON_RE = re.compile(r"\b(?:i|my|me|mine|myself)\b", re.IGNORECASE)
PROPER_NAME_RE = re.compile(r"(?:^|\s)([A-Z][a-z]{2,})\b")
NON_NAME_WORDS = {
    "The", "What", "How", "When", "Where", "Why", "Can", "Could", "Would",
    "Should", "Is", "Are", "Was", "Were", "Do", "Does", "Did", "Hello", "Hi",
    "Hey", "Please", "Fact", "Check", "Verify",
}

ApprovalPrompt = Callable[
    [str, str, str],
    Union[Awaitable[bool], bool],
]


def sanitize_topic(value: str) -> str:
    """PR_1 / PR_2 — topic-only query with personal identifiers removed."""

    sanitized = EMAIL_RE.sub("[email]", value)
    sanitized = PHONE_RE.sub("[phone]", sanitized)
    sanitized = redact_home_paths(sanitized)
    sanitized = PERSONAL_NAME_RE.sub("[person]", sanitized)
    sanitized = PROPER_NAME_RE.sub(" [person]", sanitized)
    return sanitized.strip()


def contains_personal_context(value: str) -> bool:
    """Detect whether text likely includes personal context."""

    if any(
        pattern.search(value)
        for pattern in (EMAIL_RE, PHONE_RE, *HOME_PATH_PATTERNS, PERSONAL_NAME_RE, FIRST_PERSON_RE)
    ):
        return True
    for match in PROPER_NAME_RE.finditer(value):
        if match.group(1) not in NON_NAME_WORDS:
            return True
    return False


class PrivacyGate:
    """Screens outbound requests before they leave the system."""

    def __init__(
        self,
        *,
        approval_prompt: ApprovalPrompt | None = None,
    ) -> None:
        self._approval_prompt = approval_prompt
        self._pending: dict[str, PrivacyDecision] = {}

    async def screen_outbound(
        self,
        destination: str,
        query: str,
        *,
        reason: str = "External lookup",
    ) -> PrivacyDecision:
        sanitized = sanitize_topic(query)
        if not contains_personal_context(query):
            return PrivacyDecision(allowed=True, sanitized_query=sanitized)

        if self._approval_prompt is None:
            return PrivacyDecision(
                allowed=False,
                sanitized_query=sanitized,
                reason="Personal context detected; approval handler unavailable.",
            )

        approved = self._approval_prompt(destination, reason, sanitized)
        if hasattr(approved, "__await__"):
            approved = await approved  # type: ignore[misc]

        if not approved:
            return PrivacyDecision(
                allowed=False,
                sanitized_query=sanitized,
                reason="User denied outbound request.",
            )

        return PrivacyDecision(allowed=True, sanitized_query=sanitized)


def full_reset(wiki_dir: Path, memory_dir: Path, logs_dir: Path) -> None:
    """PR_4 — wipe behavioral logs, wiki, and personality model."""

    for path in (wiki_dir, memory_dir, logs_dir):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
