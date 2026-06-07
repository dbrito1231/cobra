"""Tests for system_control Tier 2 volume and stub operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.builtin import system_control
from tools.models import ToolCall


class TestSystemControlTier2:
    def test_notifications_unsupported_everywhere(self) -> None:
        result = system_control.handle(
            ToolCall("system_control", {"operation": "notifications"})
        )
        assert result["status"] == "unsupported"

    def test_settings_unsupported_everywhere(self) -> None:
        result = system_control.handle(
            ToolCall("system_control", {"operation": "settings"})
        )
        assert result["status"] == "unsupported"

    def test_volume_linux_pactl(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""
        with patch("tools.builtin.system_control.platform.system", return_value="Linux"):
            with patch("tools.builtin.system_control.shutil.which", return_value="/usr/bin/pactl"):
                with patch("tools.builtin.system_control._run", return_value=mock_process) as mock_run:
                    result = system_control.handle(
                        ToolCall("system_control", {"operation": "volume", "level": 50})
                    )
        assert result["status"] == "set"
        assert mock_run.call_args[0][0][0] == "pactl"

    def test_volume_windows_without_nircmd_partial(self) -> None:
        with patch("tools.builtin.system_control.platform.system", return_value="Windows"):
            with patch("tools.builtin.system_control.shutil.which", return_value=None):
                result = system_control.handle(
                    ToolCall("system_control", {"operation": "volume", "level": 40})
                )
        assert result["status"] == "partial"
        assert result["level"] == 40

    def test_brightness_still_macos_only(self) -> None:
        with patch("tools.builtin.system_control.platform.system", return_value="Linux"):
            result = system_control.handle(
                ToolCall("system_control", {"operation": "brightness", "level": 80})
            )
        assert result["status"] == "unsupported"
