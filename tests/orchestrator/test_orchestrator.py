"""Tests for the Orchestrator component."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from orchestrator.event_bus import EventBus
from orchestrator.lifecycle_log import LifecycleLogger
from orchestrator.models import (
    ComponentName,
    FailureAction,
    HealthState,
    LifecycleEventType,
    StartupPhase,
)
from orchestrator.orchestrator import Orchestrator
from orchestrator.registry import ComponentRegistry
from orchestrator.startup import StartupHooks


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "orchestrator.log"


class TestComponentRegistry:
    def test_dependency_graph(self) -> None:
        registry = ComponentRegistry()
        assert registry.dependencies_ready(ComponentName.CONFIGURATION)
        assert not registry.dependencies_ready(ComponentName.BRAIN)

        registry.mark_state(ComponentName.CONFIGURATION, HealthState.HEALTHY)
        registry.mark_state(ComponentName.MCP, HealthState.HEALTHY)
        assert registry.dependencies_ready(ComponentName.BRAIN)


class TestEventBus:
    def test_routes_events_to_subscribers(self) -> None:
        bus = EventBus()
        received: list = []
        bus.subscribe("pipeline.step", received.append)
        event = bus.route(
            "pipeline.step",
            ComponentName.BRAIN,
            {"step": "reasoning"},
        )
        assert received == [event]


class TestLifecycleLogger:
    def test_append_entry(self, log_path: Path) -> None:
        logger = LifecycleLogger(log_path)
        logger.log(
            ComponentName.SECURITY,
            LifecycleEventType.START,
            trigger="startup",
            outcome="success",
        )
        entries = logger.read_entries()
        assert entries[0]["component"] == "security"


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_phased_startup_reaches_ready(self, log_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("COBRA_SKIP_LM_STUDIO", "1")
        started: list[ComponentName] = []

        hooks = StartupHooks(
            load_configuration=lambda: started.append(ComponentName.CONFIGURATION),
            initialize_security=lambda: started.append(ComponentName.SECURITY),
            initialize_mcp=lambda: started.append(ComponentName.MCP),
            wait_lm_studio=lambda: True,
            initialize_brain=lambda: started.append(ComponentName.BRAIN),
            initialize_tools=lambda: started.append(ComponentName.TOOLS),
            initialize_voice=lambda: started.append(ComponentName.VOICE),
            initialize_chat_ui=lambda: started.append(ComponentName.CHAT_UI),
        )
        orchestrator = Orchestrator(hooks=hooks, log_path=log_path)
        assert await orchestrator.start()
        assert orchestrator.ready
        assert orchestrator.phase == StartupPhase.READY
        assert ComponentName.SECURITY in started
        assert ComponentName.VOICE in started
        await orchestrator.shutdown()
        assert not orchestrator.ready

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self, log_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("COBRA_SKIP_LM_STUDIO", "1")
        orchestrator = Orchestrator(
            hooks=StartupHooks(wait_lm_studio=lambda: True),
            log_path=log_path,
        )
        payloads: list = []
        orchestrator.subscribe("system.ready", lambda event: payloads.append(event.payload))
        await orchestrator.start()
        assert payloads
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_health_monitor_marks_degraded(self, log_path: Path) -> None:
        orchestrator = Orchestrator(
            hooks=StartupHooks(wait_lm_studio=lambda: True),
            log_path=log_path,
            health_providers={
                ComponentName.VOICE: lambda: (True, "missing model", True),
            },
        )
        orchestrator.health.register(
            ComponentName.VOICE,
            lambda: (True, "missing model", True),
        )
        states = orchestrator.health.check_once()
        assert states[ComponentName.VOICE] == HealthState.DEGRADED

    @pytest.mark.asyncio
    async def test_restart_component(self, log_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("COBRA_SKIP_LM_STUDIO", "1")
        calls = {"count": 0}

        def init_security() -> None:
            calls["count"] += 1

        hooks = StartupHooks(
            initialize_security=init_security,
            wait_lm_studio=lambda: True,
        )
        orchestrator = Orchestrator(hooks=hooks, log_path=log_path)
        await orchestrator.start()
        assert await orchestrator.restart_component(ComponentName.SECURITY)
        assert calls["count"] == 2
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_bootstrap_builds_orchestrator(self, monkeypatch) -> None:
        monkeypatch.setenv("COBRA_SKIP_LM_STUDIO", "1")
        from orchestrator.bootstrap import build_default_orchestrator

        config_dict = {
            "version": "1.0",
            "active_profile": "default",
            "profiles": {
                "default": {
                    "name": "Default",
                    "model": {
                        "provider": "lm_studio",
                        "endpoint": "http://127.0.0.1:1234",
                        "model_id": "test",
                    },
                    "api_keys": {
                        "claude": "sk-test-claude-key",
                        "copilot": "copilot-test-key",
                    },
                    "storage": {
                        "wiki_dir": "/tmp/cobra-test/wiki",
                        "memory_dir": "/tmp/cobra-test/memory",
                        "logs_dir": "/tmp/cobra-test/logs",
                        "backups_dir": "/tmp/cobra-test/backups",
                    },
                }
            },
        }
        orchestrator = build_default_orchestrator(config_dict=config_dict)
        assert await orchestrator.start()
        await orchestrator.shutdown()
