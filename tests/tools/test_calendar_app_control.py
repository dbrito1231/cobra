"""Tests for calendar and app_control built-in tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.builtin import app_control, calendar
from tools.models import ToolCall
from tools.registry import classify_tool_call
from tools.models import ActionType


@pytest.fixture
def calendar_paths(tmp_path, monkeypatch):
    store_path = tmp_path / "calendar" / "events.json"
    monkeypatch.setattr("tools.builtin.calendar_store.events_path", lambda: store_path)
    monkeypatch.setattr(
        "tools.builtin.calendar_store.calendar_dir",
        lambda: store_path.parent,
    )
    return store_path


class TestCalendarTool:
    def test_read_empty_calendar(self, calendar_paths) -> None:
        result = calendar.handle(ToolCall("calendar", {"operation": "read"}))
        assert result["status"] == "ok"
        assert result["events"] == []

    def test_create_and_read_event(self, calendar_paths) -> None:
        created = calendar.handle(
            ToolCall(
                "calendar",
                {
                    "operation": "create",
                    "title": "Standup",
                    "starts_at": "2026-06-06T09:00:00+00:00",
                    "duration_minutes": 30,
                },
            )
        )
        assert created["status"] == "created"
        assert created["event"]["title"] == "Standup"

        listed = calendar.handle(ToolCall("calendar", {"operation": "list"}))
        assert listed["event_count"] == 1

    def test_check_schedule(self, calendar_paths) -> None:
        calendar.handle(
            ToolCall(
                "calendar",
                {
                    "operation": "create",
                    "title": "Review",
                    "starts_at": "2026-06-06T14:00:00+00:00",
                    "duration_minutes": 60,
                },
            )
        )
        schedule = calendar.handle(
            ToolCall(
                "calendar",
                {"operation": "check", "date": "2026-06-06T00:00:00+00:00"},
            )
        )
        assert schedule["event_count"] == 1

    def test_update_and_delete(self, calendar_paths) -> None:
        created = calendar.handle(
            ToolCall(
                "calendar_write",
                {
                    "title": "Draft",
                    "starts_at": "2026-06-07T10:00:00+00:00",
                    "duration_minutes": 15,
                },
            )
        )
        event_id = created["event"]["id"]

        updated = calendar.handle(
            ToolCall(
                "calendar",
                {"operation": "update", "event_id": event_id, "title": "Final"},
            )
        )
        assert updated["event"]["title"] == "Final"

        deleted = calendar.handle(
            ToolCall("calendar", {"operation": "delete", "event_id": event_id})
        )
        assert deleted["status"] == "deleted"

    def test_calendar_read_is_read_only(self) -> None:
        assert classify_tool_call(ToolCall("calendar_read", {"operation": "read"})) == ActionType.READ_ONLY

    def test_calendar_create_is_destructive(self) -> None:
        assert classify_tool_call(ToolCall("calendar", {"operation": "create"})) == ActionType.DESTRUCTIVE

    def test_calendar_default_operation_is_read_only(self) -> None:
        assert classify_tool_call(ToolCall("calendar", {})) == ActionType.READ_ONLY


class TestAppControlTool:
    def test_list_is_read_only(self) -> None:
        assert classify_tool_call(ToolCall("app_control", {"operation": "list"})) == ActionType.READ_ONLY

    def test_open_requires_app_name(self) -> None:
        with pytest.raises(ValueError, match="app_name"):
            app_control.handle(ToolCall("app_control", {"operation": "open"}))

    def test_open_macos(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""
        with patch("tools.builtin.app_control.platform.system", return_value="Darwin"):
            with patch("tools.builtin.app_control._run", return_value=mock_process) as mock_run:
                result = app_control.handle(
                    ToolCall("app_control", {"operation": "open", "app_name": "Calculator"})
                )
        assert result["status"] == "opened"
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0][:2] == ["open", "-a"]

    def test_close_macos(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""
        with patch("tools.builtin.app_control.platform.system", return_value="Darwin"):
            with patch("tools.builtin.app_control._run", return_value=mock_process):
                result = app_control.handle(
                    ToolCall("app_control", {"operation": "close", "app_name": "Calculator"})
                )
        assert result["status"] == "closed"

    def test_open_linux(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""
        with patch("tools.builtin.app_control.platform.system", return_value="Linux"):
            with patch("tools.builtin.app_control._run", return_value=mock_process) as mock_run:
                result = app_control.handle(
                    ToolCall("app_control", {"operation": "open", "app_name": "firefox"})
                )
        assert result["status"] == "opened"
        assert mock_run.call_args[0][0] == ["xdg-open", "firefox"]

    def test_list_macos(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Finder, Safari"
        mock_process.stderr = ""
        with patch("tools.builtin.app_control.platform.system", return_value="Darwin"):
            with patch("tools.builtin.app_control._run", return_value=mock_process):
                result = app_control.handle(ToolCall("app_control", {"operation": "list"}))
        assert result["applications"] == ["Finder", "Safari"]

    def test_open_windows(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""
        with patch("tools.builtin.app_control.platform.system", return_value="Windows"):
            with patch("tools.builtin.app_control._run", return_value=mock_process) as mock_run:
                result = app_control.handle(
                    ToolCall("app_control", {"operation": "open", "url": "https://example.com"})
                )
        assert result["status"] == "opened"
        assert mock_run.call_args[0][0][:3] == ["cmd", "/c", "start"]

    def test_close_windows(self) -> None:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""
        with patch("tools.builtin.app_control.platform.system", return_value="Windows"):
            with patch("tools.builtin.app_control._run", return_value=mock_process) as mock_run:
                result = app_control.handle(
                    ToolCall("app_control", {"operation": "close", "app_name": "notepad.exe"})
                )
        assert result["status"] == "closed"
        assert mock_run.call_args[0][0][:2] == ["taskkill", "/IM"]
