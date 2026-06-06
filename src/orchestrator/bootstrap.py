"""Bootstrap C.O.B.R.A. with security, voice, and chat UI hooks."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from chat_ui.config import ChatUIConfig
from chat_ui.models import VoiceState, WebSocketEvent
from chat_ui.server import ChatUIServer
from orchestrator.models import ComponentName
from orchestrator.orchestrator import Orchestrator
from orchestrator.startup import StartupHooks
from security.config import SecurityConfig
from security.service import SecurityService
from voice.config import VoiceConfig
from voice.models import SessionState, TranscribedTextEvent
from voice.service import VoiceService


def build_default_orchestrator(config: dict[str, Any] | None = None) -> Orchestrator:
    """Wire implemented components with stub hooks for pending ones."""

    config = config or {}
    security = SecurityService(SecurityConfig.from_config_dict(config))
    voice = VoiceService(
        VoiceConfig.from_config_dict(config),
        input_allowed=security.is_input_allowed,
    )
    ui_config = ChatUIConfig.from_config_dict(config)
    ui_config = ChatUIConfig(
        host=security.bind_host,
        port=ui_config.port,
        wiki_dir=ui_config.wiki_dir,
        sessions_dir=ui_config.sessions_dir,
        profile_name=ui_config.profile_name,
        open_browser=ui_config.open_browser,
    )
    chat_ui = ChatUIServer(ui_config)

    async def voice_input_handler(event: TranscribedTextEvent) -> None:
        message = chat_ui.session_store.add_message("user", event.text)
        await chat_ui.push_event(WebSocketEvent.message(message))

    voice._input_handler = voice_input_handler  # noqa: SLF001 — bootstrap wiring

    def map_voice_state(state: SessionState) -> None:
        mapping = {
            SessionState.PASSIVE: VoiceState.IDLE,
            SessionState.ACTIVE: VoiceState.LISTENING,
            SessionState.RESPONDING: VoiceState.SPEAKING,
        }
        asyncio.get_event_loop().create_task(
            chat_ui.set_voice_state(mapping[state])
        )

    voice._on_voice_state = map_voice_state  # noqa: SLF001

    hooks = StartupHooks(
        load_configuration=lambda: None,
        initialize_security=security.initialize,
        initialize_mcp=lambda: None,
        wait_lm_studio=lambda: _lm_studio_reachable(config),
        initialize_brain=lambda: None,
        initialize_tools=lambda: None,
        initialize_voice=voice.initialize,
        initialize_chat_ui=lambda: chat_ui.start(),
        stop_chat_ui=chat_ui.stop,
        stop_voice=voice.shutdown,
        stop_tools=lambda: None,
        stop_brain=lambda: None,
        stop_mcp=lambda: None,
        stop_security=security.shutdown,
        save_configuration=lambda: None,
    )

    health_providers = {
        ComponentName.SECURITY: lambda: _health_tuple(security.health()),
        ComponentName.VOICE: lambda: _health_tuple(voice.health()),
        ComponentName.CHAT_UI: lambda: (True, "ok", False),
    }

    return Orchestrator(hooks=hooks, health_providers=health_providers)


def _health_tuple(status) -> tuple[bool, str, bool]:
    return status.healthy, status.message, status.degraded


def _lm_studio_reachable(config: dict[str, Any]) -> bool:
    if os.environ.get("COBRA_SKIP_LM_STUDIO", "0") == "1":
        return True
    model = config.get("model") or {}
    endpoint = model.get("endpoint", "http://127.0.0.1:1234")
    try:
        import httpx

        response = httpx.get(f"{endpoint.rstrip('/')}/v1/models", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


async def main() -> None:
    orchestrator = build_default_orchestrator()
    started = await orchestrator.start()
    if not started:
        return
    try:
        while orchestrator.ready:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await orchestrator.shutdown()
