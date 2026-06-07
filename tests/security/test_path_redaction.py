"""Tests for cross-platform path redaction."""

from __future__ import annotations

from security.path_redaction import redact_home_paths


class TestPathRedaction:
    def test_macos_home(self) -> None:
        assert redact_home_paths("/Users/damian/project") == "[home]/project"

    def test_linux_home(self) -> None:
        assert redact_home_paths("/home/damian/project") == "[home]/project"

    def test_windows_home(self) -> None:
        assert redact_home_paths(r"C:\Users\damian\project") == "[home]\\project"

    def test_tilde_home(self) -> None:
        assert redact_home_paths("~/Documents/file.txt") == "[home]/Documents/file.txt"
