"""Cross-platform home-path redaction per specs/platform-support.md §9."""

from __future__ import annotations

import re

MAC_HOME_RE = re.compile(r"/Users/[^/\s]+")
LINUX_HOME_RE = re.compile(r"/home/[^/\s]+")
WINDOWS_HOME_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+")
TILDE_HOME_RE = re.compile(r"(?<![\w.])~(?:/|\\|$)")


def redact_home_paths(value: str) -> str:
    """Replace user-home path segments with [home]."""

    sanitized = MAC_HOME_RE.sub("[home]", value)
    sanitized = LINUX_HOME_RE.sub("[home]", sanitized)
    sanitized = WINDOWS_HOME_RE.sub("[home]", sanitized)
    sanitized = TILDE_HOME_RE.sub("[home]/", sanitized)
    return sanitized
