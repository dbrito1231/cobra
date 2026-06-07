"""Tests for ToolsService lifecycle and wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.models import CobraConfig, ProfileConfig
from config.reader import ConfigReader
from tools.config import ToolsConfig, reset_session_sandbox
from tools.models import ActionType, ToolCall
from tools.registry import classify_tool_call
from tools.privacy import configure_paths, local_tool_log_path, wiki_tool_log_path
from tools.service import ToolsService


@pytest.fixture(autouse=True)
def clear_session_sandbox():
    reset_session_sandbox()
    yield
    reset_session_sandbox()


@pytest.fixture
def tools_dirs(tmp_path: Path) -> dict[str, Path]:
    wiki = tmp_path / "wiki"
    memory = tmp_path / "memory"
    logs = tmp_path / "logs"
    for path in (wiki, memory, logs):
        path.mkdir()
    return {"wiki_dir": wiki, "memory_dir": memory, "logs_dir": logs}


@pytest.fixture
def config_reader(tools_dirs: dict[str, Path]) -> ConfigReader:
    config = CobraConfig(
        profiles={
            "default": ProfileConfig(
                storage={
                    "wiki_dir": str(tools_dirs["wiki_dir"]),
                    "memory_dir": str(tools_dirs["memory_dir"]),
                    "logs_dir": str(tools_dirs["logs_dir"]),
                    "backups_dir": str(tools_dirs["logs_dir"] / "backups"),
                },
                tool_sandbox=True,
            )
        }
    )
    return ConfigReader(config)


class TestToolsConfig:
    def test_from_config_dict(self, tools_dirs: dict[str, Path]) -> None:
        config = ToolsConfig.from_config_dict(
            {
                "storage": {
                    "wiki_dir": str(tools_dirs["wiki_dir"]),
                    "logs_dir": str(tools_dirs["logs_dir"]),
                },
                "tool_sandbox": False,
            }
        )
        assert config.sandbox_enabled is False


class TestToolsService:
    def test_initialize_configures_paths(
        self,
        config_reader: ConfigReader,
        tools_dirs: dict[str, Path],
    ) -> None:
        service = ToolsService(config_reader)
        service.initialize()
        assert wiki_tool_log_path() == tools_dirs["wiki_dir"] / "tools-log.md"
        assert local_tool_log_path() == tools_dirs["logs_dir"] / "tools-log.jsonl"
        service.shutdown()

    def test_health_after_init(self, config_reader: ConfigReader) -> None:
        service = ToolsService(config_reader)
        assert not service.health().healthy
        service.initialize()
        assert service.health().healthy
        service.shutdown()
        assert not service.health().healthy

    def test_session_sandbox_override(self, config_reader: ConfigReader) -> None:
        service = ToolsService(config_reader)
        service.initialize()
        assert service.config.sandbox_enabled is True
        service.set_session_sandbox(False)
        assert service.config.sandbox_enabled is False
        service.set_session_sandbox(None)
        assert service.config.sandbox_enabled is True
        service.shutdown()

    @pytest.mark.asyncio
    async def test_execute_read_only_tool(self, config_reader: ConfigReader, tmp_path: Path) -> None:
        service = ToolsService(config_reader)
        service.initialize()
        test_file = tmp_path / "hello.txt"
        test_file.write_text("hi", encoding="utf-8")
        call = ToolCall(
            "file_management",
            {"operation": "read", "path": str(test_file), "sandboxed": False},
            sandboxed=False,
        )
        result = await service.execute_tool(call)
        assert result.success
        service.shutdown()


class TestSystemControlApproval:
    def test_volume_is_destructive(self) -> None:
        call = ToolCall("system_control", {"operation": "volume", "level": 50})
        assert classify_tool_call(call) is ActionType.DESTRUCTIVE

    def test_status_is_read_only(self) -> None:
        call = ToolCall("system_control", {"operation": "status"})
        assert classify_tool_call(call) is ActionType.READ_ONLY
