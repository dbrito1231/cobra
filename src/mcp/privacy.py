"""Sanitize MCP outbound queries per privacy.md PR1."""

from __future__ import annotations

import re

import re

from security.path_redaction import redact_home_paths

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")


def sanitize_query(value: str) -> str:
    sanitized = EMAIL_RE.sub("[email]", value)
    sanitized = PHONE_RE.sub("[phone]", sanitized)
    sanitized = redact_home_paths(sanitized)
    return sanitized.strip()
