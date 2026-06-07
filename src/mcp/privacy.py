"""Sanitize MCP outbound queries per privacy.md PR1."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
HOME_PATH_RE = re.compile(r"/Users/[^/\s]+")


def sanitize_query(value: str) -> str:
    sanitized = EMAIL_RE.sub("[email]", value)
    sanitized = PHONE_RE.sub("[phone]", sanitized)
    sanitized = HOME_PATH_RE.sub("[home]", sanitized)
    return sanitized.strip()
