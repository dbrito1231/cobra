"""Bootstrap C.O.B.R.A. with config, security, MCP, brain, voice, and chat UI."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from brain.service import BrainService
from chat_ui.config import ChatUIConfig
from chat_ui.models import (
    ApprovalRequestPayload,
    ComponentHealthEntry,
    FailurePromptPayload,
    McpServerStatus,
    McpStatus,
    ProactiveItem,
    VoiceState,
    WebSocketEvent,
)
from chat_ui.server import ChatUIServer
from config.lm_studio import LmStudioWaiter
from config.loader import DEFAULT_CONFIG_PATH, load_config
from config.models import CobraConfig
from config.service import ConfigService
from mcp.models import McpApprovalRequest
from mcp.service import McpService
from orchestrator.approval_wait import ApprovalWaitRegistry
from orchestrator.failure_wait import FailureWaitRegistry
from orchestrator.models import BusEvent, ComponentName, FailureAction, HealthState
from orchestrator.onboarding import OnboardingManager
from orchestrator.orchestrator import Orchestrator
from orchestrator.startup import StartupHooks
from orchestrator.ui_bridge import schedule_ui
from security.config import SecurityConfig
from security.service import SecurityService
from tools.service import ToolsService
from voice.config import VoiceConfig
from voice.models import SessionState, TranscribedTextEvent
from voice.service import VoiceService


def build_default_orchestrator(
    config_path: Path | None = None,
    *,
    config_dict: dict[str, Any] | None = None,
) -> Orchestrator:
    """Wire implemented components; config_dict bypasses disk for tests."""

    config_service = ConfigService(config_path or DEFAULT_CONFIG_PATH)
    if config_dict is not None:
        config_service.config = CobraConfig.from_dict(config_dict)
        config_service.reader.replace(config_service.config)
    elif config_service.config_path.exists():
        config_service.config = load_config(config_service.config_path)
        config_service.reader.replace(config_service.config)

    legacy = config_service.to_legacy_dict() if config_service.config else {}
    cobra_dir = Path.home() / ".cobra"
    storage = legacy.get("storage", {})
    if storage.get("memory_dir"):
        cobra_dir = Path(storage["memory_dir"]).parent
    elif storage.get("wiki_dir"):
        cobra_dir = Path(storage["wiki_dir"]).parent
    onboarding = OnboardingManager(cobra_dir / "onboarding_state.json")

    chat_ui_holder: dict[str, ChatUIServer] = {}
    approval_waits = ApprovalWaitRegistry()
    failure_waits = FailureWaitRegistry()
    lm_waiter_holder: dict[str, LmStudioWaiter] = {}

    async def mcp_approval_prompt(request: McpApprovalRequest) -> bool:
        ui = chat_ui_holder.get("chat_ui")
        if ui is None:
            return False
        payload = ApprovalRequestPayload(
            event_id=request.event_id,
            what=f"MCP call: {request.server_name}",
            why=request.reason,
            data_summary=request.sanitized_query,
            action_type="mcp_call",
        )
        future = approval_waits.register(request.event_id)
        await ui.push_approval_request(payload)
        return await future

    async def brain_approval_prompt(destination: str, reason: str, summary: str) -> bool:
        ui = chat_ui_holder.get("chat_ui")
        if ui is None:
            return False
        event_id = str(uuid4())
        payload = ApprovalRequestPayload(
            event_id=event_id,
            what=f"Outbound: {destination}",
            why=reason,
            data_summary=summary,
            action_type="brain_outbound",
        )
        future = approval_waits.register(event_id)
        await ui.push_approval_request(payload)
        return await future

    wiki_dir = Path(legacy.get("storage", {}).get("wiki_dir", Path.home() / ".cobra" / "wiki"))

    def on_lock() -> None:
        ui = chat_ui_holder.get("chat_ui")
        if ui:
            schedule_ui(ui, lambda: ui.set_locked(True))

    def on_unlock() -> None:
        ui = chat_ui_holder.get("chat_ui")
        if ui:
            schedule_ui(ui, lambda: ui.set_locked(False))

    def on_anomaly(alert) -> None:
        ui = chat_ui_holder.get("chat_ui")
        if ui:
            schedule_ui(
                ui,
                lambda: ui.push_anomaly_alert(alert.destination, alert.sanitized_detail),
            )

    security = SecurityService(
        SecurityConfig.from_config_dict(legacy),
        on_lock=on_lock,
        on_unlock=on_unlock,
        on_anomaly=on_anomaly,
    )

    def mcp_validation_failure(failures: list[tuple[str, bool, str]]) -> None:
        ui = chat_ui_holder.get("chat_ui")
        if ui is None:
            return
        names = ", ".join(name for name, ok, _msg in failures if not ok)
        schedule_ui(
            ui,
            lambda: ui.push_anomaly_alert(
                "mcp_validation",
                f"MCP server validation failed: {names}",
            ),
        )

    mcp = McpService(
        wiki_dir=wiki_dir,
        approval_prompt=mcp_approval_prompt,
        audit_outbound=security.audit_outbound,
        on_validation_failure=mcp_validation_failure,
    )

    tools = ToolsService(
        config_service.reader,
        audit_outbound=security.audit_outbound,
    )

    brain = BrainService(
        config_service.reader,
        mcp_service=mcp,
        tools_service=tools,
        audit_outbound=security.audit_outbound,
        approval_prompt=brain_approval_prompt,
        offline=os.environ.get("COBRA_BRAIN_OFFLINE", "0") == "1",
        onboarding=onboarding,
    )

    voice = VoiceService(
        VoiceConfig.from_config_dict(legacy),
        input_allowed=security.is_input_allowed,
    )
    ui_config = ChatUIConfig.from_config_dict(legacy)
    ui_config = ChatUIConfig(
        host=security.bind_host,
        port=ui_config.port,
        wiki_dir=ui_config.wiki_dir,
        sessions_dir=ui_config.sessions_dir,
        profile_name=ui_config.profile_name,
        open_browser=ui_config.open_browser,
    )
    chat_ui = ChatUIServer(ui_config)
    chat_ui_holder["chat_ui"] = chat_ui
    chat_ui.set_input_allowed(security.is_input_allowed)

    orchestrator_holder: dict[str, Orchestrator] = {}

    async def voice_input_handler(event: TranscribedTextEvent) -> None:
        security.record_activity()
        orch = orchestrator_holder.get("orchestrator")
        if orch:
            orch.set_response_in_progress(True)
        user_message = chat_ui.session_store.add_message("user", event.text)
        await chat_ui.push_event(WebSocketEvent.message(user_message))
        try:
            events = await brain.process_voice_event(event)
            for ws_event in events:
                if ws_event.type == "message" and ws_event.payload.get("sender") == "cobra":
                    chat_ui.session_store.add_message("cobra", ws_event.payload.get("content", ""))
                await chat_ui.push_event(ws_event)
        finally:
            if orch:
                orch.set_response_in_progress(False)

    voice._input_handler = voice_input_handler  # noqa: SLF001

    def map_voice_state(state: SessionState) -> None:
        mapping = {
            SessionState.PASSIVE: VoiceState.IDLE,
            SessionState.ACTIVE: VoiceState.LISTENING,
            SessionState.RESPONDING: VoiceState.SPEAKING,
        }
        schedule_ui(chat_ui, lambda: chat_ui.set_voice_state(mapping[state]))

    voice._on_voice_state = map_voice_state  # noqa: SLF001

    async def brain_input_handler(text: str) -> list[WebSocketEvent]:
        security.record_activity()
        orch = orchestrator_holder.get("orchestrator")
        if orch:
            orch.set_response_in_progress(True)
        try:
            events = await brain.process_input(text)
            for ws_event in events:
                if ws_event.type == "message" and ws_event.payload.get("sender") == "cobra":
                    chat_ui.session_store.add_message("cobra", ws_event.payload.get("content", ""))
            return events
        finally:
            if orch:
                orch.set_response_in_progress(False)

    chat_ui.set_input_handler(brain_input_handler)

    async def approval_handler(event_id: str, approved: bool) -> None:
        if approval_waits.resolve(event_id, approved):
            return
        await tools.resolve_approval(event_id, approved)
        await mcp.resolve_approval(event_id, approved)

    chat_ui.set_approval_handler(approval_handler)

    async def failure_handler(event_id: str, action: str) -> None:
        failure_waits.resolve(event_id, action)

    async def failure_prompt(name: ComponentName, state: HealthState, message: str) -> FailureAction:
        ui = chat_ui_holder.get("chat_ui")
        if ui is None:
            return FailureAction.IGNORE
        event_id = str(uuid4())
        payload = FailurePromptPayload(
            event_id=event_id,
            component=name.value,
            state=state.value,
            message=message,
        )
        future = failure_waits.register(event_id)
        await ui.push_failure_prompt(payload)
        action = await future
        mapping = {
            "restart_component": FailureAction.RESTART_COMPONENT,
            "restart_all": FailureAction.RESTART_ALL,
        }
        return mapping.get(action, FailureAction.IGNORE)

    async def on_proactive_surfaced() -> None:
        item = brain.proactivity.surface_next(user_asked=True)
        if item is None:
            return
        events = await brain.deliver_proactive(
            ProactiveItem(id=item.id, preview=item.preview, priority=item.priority)
        )
        for ws_event in events:
            if ws_event.type == "message" and ws_event.payload.get("sender") == "cobra":
                chat_ui.session_store.add_message("cobra", ws_event.payload.get("content", ""))
            await chat_ui.push_event(ws_event)

    chat_ui.set_proactive_handler(on_proactive_surfaced)
    chat_ui.set_failure_handler(failure_handler)

    def push_onboarding_state() -> None:
        onboarding.sync(
            voice=voice,
            brain=brain,
            needs_wizard=config_service.needs_wizard,
        )
        payload = brain.onboarding_payload()
        schedule_ui(
            chat_ui,
            lambda: chat_ui.push_onboarding_step(payload),
        )

    async def voice_enrollment_approve() -> dict[str, Any]:
        voice.cloning.approve_clone()
        onboarding.mark_voice_complete()
        push_onboarding_state()
        auto_events = await brain._maybe_auto_start_seed()  # noqa: SLF001
        if auto_events:
            for ws_event in auto_events:
                await chat_ui.push_event(ws_event)
        return {"status": "ok", **voice.enrollment_status()}

    def voice_enrollment_reject() -> dict[str, Any]:
        voice.cloning.reject_clone()
        push_onboarding_state()
        return {"status": "ok", **voice.enrollment_status()}

    def voice_enrollment_train() -> dict[str, Any]:
        trained = voice.cloning.train_local_model()
        push_onboarding_state()
        return {"status": "ok" if trained else "failed", **voice.enrollment_status()}

    def voice_enrollment_test() -> dict[str, Any]:
        import base64

        audio = voice.cloning.synthesize_test_phrase() or b""
        return {
            "status": "ok",
            "audio_base64": base64.b64encode(audio).decode(),
            **voice.enrollment_status(),
        }

    chat_ui.set_voice_enrollment_handlers(
        status=voice.enrollment_status,
        sample=lambda wav, duration=None: voice.cloning.record_sample_bytes(wav, duration),
        train=voice_enrollment_train,
        approve=voice_enrollment_approve,
        reject=voice_enrollment_reject,
        test_playback=voice_enrollment_test,
    )
    chat_ui.set_onboarding_handlers(
        status=brain.onboarding_payload,
        notify=push_onboarding_state,
    )

    async def voice_deliver(text: str, mood_ctx: dict[str, Any]) -> None:
        from voice.models import MoodResult, MoodLevel

        mood = MoodResult(
            mood=MoodLevel(mood_ctx.get("mood", "neutral")),
            energy=float(mood_ctx.get("energy", 0.5)),
            speaking_rate=float(mood_ctx.get("speaking_rate", 1.0)),
        )
        await voice.deliver_response(text, mood)

    brain._on_voice_deliver = voice_deliver  # noqa: SLF001

    def push_mcp_statuses() -> None:
        statuses = [
            McpServerStatus(
                name=item["name"],
                status=McpStatus.ONLINE if item["status"] == "available" else McpStatus.OFFLINE,
            )
            for item in mcp.status_snapshot()
        ]
        schedule_ui(chat_ui, lambda: chat_ui.set_mcp_servers(statuses))

    def load_configuration() -> None:
        if config_service._initialized and not config_service.needs_wizard:
            return
        if config_dict is not None:
            from config.validation import validate_config

            report = validate_config(config_service.config, skip_lm_studio=True)
            if report.passed:
                config_service._initialized = True
            else:
                failures = "; ".join(item.message for item in report.failures())
                raise RuntimeError(f"Configuration validation failed: {failures}")
            return

        report = config_service.initialize()
        if config_service.needs_wizard:
            schedule_ui(
                chat_ui,
                lambda: chat_ui.push_config_notify("First-time setup required. Complete the wizard."),
            )
            return
        if not report.passed and not report.lm_studio_unreachable:
            failures = "; ".join(item.message for item in report.failures())
            raise RuntimeError(f"Configuration validation failed: {failures}")

    def on_config_applied(_config: CobraConfig) -> None:
        mcp.reload_servers(config_service.reader.mcp_servers())
        push_mcp_statuses()

    config_service.set_on_config_applied(on_config_applied)
    config_service.set_notify_handlers(
        on_notify=lambda msg: schedule_ui(chat_ui, lambda: chat_ui.push_config_notify(msg)),
        on_reverted=lambda msg: schedule_ui(
            chat_ui,
            lambda: chat_ui.push_config_notify(f"Config reverted: {msg}"),
        ),
    )

    async def wizard_complete(payload: dict[str, Any]) -> dict[str, Any]:
        from config.wizard import WizardInput
        from chat_ui.models import WebSocketEvent

        data = WizardInput(
            model_endpoint=payload.get("model_endpoint", "http://127.0.0.1:1234"),
            model_id=payload.get("model_id", ""),
            claude_api_key=payload.get("claude_api_key", ""),
            copilot_api_key=payload.get("copilot_api_key", ""),
            profile_name=payload.get("profile_name", "default"),
            display_name=payload.get("display_name", "Default"),
            wiki_dir=payload.get("wiki_dir", str(Path.home() / ".cobra" / "wiki")),
            memory_dir=payload.get("memory_dir", str(Path.home() / ".cobra" / "memory")),
            logs_dir=payload.get("logs_dir", str(Path.home() / ".cobra" / "logs")),
            backups_dir=payload.get("backups_dir", str(Path.home() / ".cobra" / "backups")),
        )
        report = config_service.complete_wizard(data)
        if not report.passed:
            failures = "; ".join(item.message for item in report.failures())
            return {"status": "failed", "message": failures}
        push_onboarding_state()
        return {"status": "ok"}

    chat_ui.set_wizard_handler(wizard_complete)
    chat_ui.set_wizard_status_handler(
        lambda: {"needs_wizard": config_service.needs_wizard},
    )
    chat_ui.set_seed_export_handler(brain.seed_export)
    chat_ui.set_seed_status_handler(brain.seed.seed_status)

    def initialize_mcp() -> None:
        servers = config_service.reader.mcp_servers()
        mcp.initialize(servers)
        push_mcp_statuses()

    def wait_lm_studio() -> bool:
        if os.environ.get("COBRA_SKIP_LM_STUDIO", "0") == "1":
            return True
        if config_service.needs_wizard:
            return True
        if config_service.config is None:
            return False
        waiter = LmStudioWaiter(
            config_service.config,
            on_notify=lambda msg: schedule_ui(
                chat_ui,
                lambda: chat_ui.set_lm_studio_wait(waiting=True, message=msg),
            ),
        )
        lm_waiter_holder["waiter"] = waiter
        ready = waiter.is_ready()
        if ready:
            schedule_ui(chat_ui, lambda: chat_ui.set_lm_studio_wait(waiting=False, message=""))
        return ready

    async def lm_studio_cancel() -> None:
        waiter = lm_waiter_holder.get("waiter")
        if waiter:
            waiter.cancel()
        orch = orchestrator_holder.get("orchestrator")
        if orch:
            orch.cancel_lm_wait()
        await chat_ui.set_lm_studio_wait(waiting=False, message="Wait cancelled")

    chat_ui.set_lm_studio_cancel_handler(lm_studio_cancel)

    def initialize_brain() -> None:
        brain.initialize()
        push_onboarding_state()
        schedule_ui(
            chat_ui,
            lambda: chat_ui.push_event(
                WebSocketEvent.seed_mode(brain._seed_mode_payload())  # noqa: SLF001
            ),
        )

    hooks = StartupHooks(
        load_configuration=load_configuration,
        initialize_security=security.initialize,
        initialize_mcp=initialize_mcp,
        wait_lm_studio=wait_lm_studio,
        initialize_brain=initialize_brain,
        initialize_tools=tools.initialize,
        initialize_voice=voice.initialize,
        initialize_chat_ui=lambda: chat_ui.start(),
        stop_chat_ui=chat_ui.stop,
        stop_voice=voice.shutdown,
        stop_tools=tools.shutdown,
        stop_brain=brain.shutdown,
        stop_mcp=mcp.shutdown,
        stop_security=security.shutdown,
        save_configuration=config_service.shutdown,
    )

    health_providers = {
        ComponentName.CONFIGURATION: lambda: _health_tuple(config_service.health()),
        ComponentName.SECURITY: lambda: _health_tuple(security.health()),
        ComponentName.MCP: lambda: _health_tuple(mcp.health()),
        ComponentName.BRAIN: lambda: _health_tuple(brain.health()),
        ComponentName.TOOLS: lambda: _health_tuple(tools.health()),
        ComponentName.VOICE: lambda: _health_tuple(voice.health()),
        ComponentName.CHAT_UI: lambda: chat_ui.health(),
    }

    orchestrator = Orchestrator(
        hooks=hooks,
        health_providers=health_providers,
        failure_prompt=failure_prompt,
    )
    orchestrator_holder["orchestrator"] = orchestrator

    def on_health(event: BusEvent) -> None:
        ui = chat_ui_holder.get("chat_ui")
        if ui is None:
            return
        components = [
            ComponentHealthEntry(
                name=record["name"],
                state=record["state"],
                message=record.get("message", ""),
            )
            for record in orchestrator.registry.snapshot()
        ]
        schedule_ui(ui, lambda: ui.set_component_health(components))

    orchestrator.subscribe("system.health", on_health)
    orchestrator._config_service = config_service  # noqa: SLF001
    orchestrator._mcp_service = mcp  # noqa: SLF001
    orchestrator._brain_service = brain  # noqa: SLF001
    orchestrator._tools_service = tools  # noqa: SLF001

    def on_summarize(_event: BusEvent) -> None:
        brain.handle_summarize_event()

    orchestrator.subscribe("brain.summarize_session", on_summarize)

    return orchestrator


def _health_tuple(status) -> tuple[bool, str, bool]:
    return status.healthy, status.message, getattr(status, "degraded", False)


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


if __name__ == "__main__":
    asyncio.run(main())
