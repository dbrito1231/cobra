"""Tests for macOS system_control built-in tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.builtin.system_control import handle
from tools.models import ToolCall


@pytest.fixture(autouse=True)
def darwin_platform():
    with patch("tools.builtin.system_control.platform.system", return_value="Darwin"):
        yield


def test_status_includes_volume_brightness_wifi():
    mock_processes = {
        ("osascript", "-e", "output volume of (get volume settings)"): MagicMock(
            returncode=0, stdout="42\n", stderr=""
        ),
        ("ioreg", "-l", "-w", "0"): MagicMock(
            returncode=0,
            stdout='"IODisplayBrightness"=0x32',
            stderr="",
        ),
        ("networksetup", "-listallhardwareports"): MagicMock(
            returncode=0,
            stdout="Hardware Port: Wi-Fi\nDevice: en0\n",
            stderr="",
        ),
        ("networksetup", "-getairportpower", "en0"): MagicMock(
            returncode=0,
            stdout="Wi-Fi Power (en0): On\n",
            stderr="",
        ),
        ("networksetup", "-getairportnetwork", "en0"): MagicMock(
            returncode=0,
            stdout="Current Wi-Fi Network: HomeNet\n",
            stderr="",
        ),
    }

    def fake_run(command, **kwargs):
        return mock_processes[tuple(command)]

    with patch("tools.builtin.system_control.subprocess.run", side_effect=fake_run):
        result = handle(ToolCall("system_control", {"operation": "status"}))

    assert result["volume"] == 42
    assert result["brightness"] == 50
    assert result["wifi"]["connected"] is True
    assert result["wifi"]["ssid"] == "HomeNet"


def test_volume_set_requires_level():
    with pytest.raises(ValueError, match="requires level"):
        handle(ToolCall("system_control", {"operation": "volume"}))


def test_volume_set_uses_osascript():
    with patch("tools.builtin.system_control.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = handle(ToolCall("system_control", {"operation": "volume", "level": 75}))

    assert result["status"] == "set"
    assert result["level"] == 75
    mock_run.assert_called_once_with(
        ["osascript", "-e", "set volume output volume 75"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def test_wifi_read_only_operation():
    mock_processes = {
        ("networksetup", "-listallhardwareports"): MagicMock(
            returncode=0,
            stdout="Hardware Port: Wi-Fi\nDevice: en0\n",
            stderr="",
        ),
        ("networksetup", "-getairportpower", "en0"): MagicMock(
            returncode=0,
            stdout="Wi-Fi Power (en0): Off\n",
            stderr="",
        ),
        ("networksetup", "-getairportnetwork", "en0"): MagicMock(
            returncode=0,
            stdout="You are not associated with an AirPort network.\n",
            stderr="",
        ),
    }

    def fake_run(command, **kwargs):
        return mock_processes[tuple(command)]

    with patch("tools.builtin.system_control.subprocess.run", side_effect=fake_run):
        result = handle(ToolCall("system_control", {"operation": "wifi"}))

    assert result["operation"] == "wifi"
    assert result["connected"] is False
    assert result["powered_on"] is False
