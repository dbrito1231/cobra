"""FastAPI server, WebSocket hub, and integration hooks for Brain/Voice."""

from __future__ import annotations

import asyncio
import threading
import webbrowser
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union, Union

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chat_ui.config import ChatUIConfig
from chat_ui.models import (
    ApprovalRequestPayload,
    ChatMessage,
    ComponentHealthEntry,
    FailurePromptPayload,
    McpServerStatus,
    McpStatus,
    OnboardingStepPayload,
    PipelineStep,
    ProactiveItem,
    VoiceState,
    WebSocketEvent,
)
from chat_ui.search import ConversationSearch
from chat_ui.session_store import SessionStore
from chat_ui.wiki import WikiService

STATIC_DIR = Path(__file__).resolve().parent / "static"

InputHandler = Callable[
    [str], Union[Awaitable[list[WebSocketEvent]], list[WebSocketEvent]]
]
ApprovalHandler = Callable[[str, bool], Union[Awaitable[None], None]]
ProactiveHandler = Callable[[], Union[Awaitable[None], None]]
FailureHandler = Callable[[str, str], Union[Awaitable[None], None]]
InputAllowed = Callable[[], bool]
LmStudioCancelHandler = Callable[[], Union[Awaitable[None], None]]
WizardHandler = Callable[[dict[str, Any]], Union[Awaitable[dict[str, Any]], dict[str, Any]]]
WizardStatusHandler = Callable[[], dict[str, Any]]
SeedExportHandler = Callable[[], dict[str, str]]
SeedStatusHandler = Callable[[], dict[str, Any]]
VoiceEnrollmentStatusHandler = Callable[[], dict[str, Any]]
VoiceEnrollmentSampleHandler = Callable[[bytes, Union[float, None]], dict[str, Any]]
VoiceEnrollmentActionHandler = Callable[[], dict[str, Any]]
OnboardingStatusHandler = Callable[[], dict[str, Any]]
OnboardingNotifyHandler = Callable[[], None]


class FailureDecision(BaseModel):
    event_id: str
    action: str = Field(description="restart_component, ignore, or restart_all")


class ChatInput(BaseModel):
    text: str = Field(min_length=1)


class ApprovalDecision(BaseModel):
    event_id: str
    approved: bool


class ConnectionManager:
    """Tracks browser WebSocket clients and broadcasts events."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: WebSocketEvent) -> None:
        payload = event.to_dict()
        async with self._lock:
            dead: list[WebSocket] = []
            for connection in self._connections:
                try:
                    await connection.send_json(payload)
                except RuntimeError:
                    dead.append(connection)
            for connection in dead:
                self._connections.discard(connection)


class ChatUIServer:
    """Local Chat UI server exposed to Brain, Voice, and Orchestrator."""

    def __init__(self, config: ChatUIConfig | None = None) -> None:
        self.config = config or ChatUIConfig.from_env()
        self.session_store = SessionStore(self.config.sessions_dir)
        self.search = ConversationSearch(self.session_store)
        self.wiki = WikiService(self.config.wiki_dir)
        self.wiki.ensure_index()

        self.pipeline_step = PipelineStep.IDLE
        self.voice_state = VoiceState.IDLE
        self.mcp_servers: list[McpServerStatus] = []
        self.proactive_queue: list[ProactiveItem] = []
        self.pending_approvals: dict[str, ApprovalRequestPayload] = {}
        self.pending_failures: dict[str, FailurePromptPayload] = {}
        self.component_health: list[ComponentHealthEntry] = []
        self.locked = False
        self.lm_studio_waiting = False
        self.lm_studio_message = ""

        self._manager = ConnectionManager()
        self._input_handler: InputHandler | None = None
        self._approval_handler: ApprovalHandler | None = None
        self._proactive_handler: ProactiveHandler | None = None
        self._failure_handler: FailureHandler | None = None
        self._input_allowed: InputAllowed | None = None
        self._lm_studio_cancel_handler: LmStudioCancelHandler | None = None
        self._wizard_handler: WizardHandler | None = None
        self._wizard_status_handler: WizardStatusHandler | None = None
        self._seed_export_handler: SeedExportHandler | None = None
        self._seed_status_handler: SeedStatusHandler | None = None
        self._voice_enrollment_status_handler: VoiceEnrollmentStatusHandler | None = None
        self._voice_enrollment_sample_handler: VoiceEnrollmentSampleHandler | None = None
        self._voice_enrollment_train_handler: VoiceEnrollmentActionHandler | None = None
        self._voice_enrollment_approve_handler: VoiceEnrollmentActionHandler | None = None
        self._voice_enrollment_reject_handler: VoiceEnrollmentActionHandler | None = None
        self._voice_enrollment_test_handler: VoiceEnrollmentActionHandler | None = None
        self._onboarding_status_handler: OnboardingStatusHandler | None = None
        self._onboarding_notify_handler: OnboardingNotifyHandler | None = None
        self._uvicorn: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        self.app = self._build_app()

    def set_input_handler(self, handler: InputHandler) -> None:
        self._input_handler = handler

    def set_approval_handler(self, handler: ApprovalHandler) -> None:
        self._approval_handler = handler

    def set_proactive_handler(self, handler: ProactiveHandler) -> None:
        self._proactive_handler = handler

    def set_failure_handler(self, handler: FailureHandler) -> None:
        self._failure_handler = handler

    def set_input_allowed(self, checker: InputAllowed) -> None:
        self._input_allowed = checker

    def set_lm_studio_cancel_handler(self, handler: LmStudioCancelHandler) -> None:
        self._lm_studio_cancel_handler = handler

    def set_wizard_handler(self, handler: WizardHandler) -> None:
        self._wizard_handler = handler

    def set_wizard_status_handler(self, handler: WizardStatusHandler) -> None:
        self._wizard_status_handler = handler

    def set_seed_export_handler(self, handler: SeedExportHandler) -> None:
        self._seed_export_handler = handler

    def set_seed_status_handler(self, handler: SeedStatusHandler) -> None:
        self._seed_status_handler = handler

    def set_voice_enrollment_handlers(
        self,
        *,
        status: VoiceEnrollmentStatusHandler,
        sample: VoiceEnrollmentSampleHandler,
        train: VoiceEnrollmentActionHandler,
        approve: VoiceEnrollmentActionHandler,
        reject: VoiceEnrollmentActionHandler,
        test_playback: VoiceEnrollmentActionHandler,
    ) -> None:
        self._voice_enrollment_status_handler = status
        self._voice_enrollment_sample_handler = sample
        self._voice_enrollment_train_handler = train
        self._voice_enrollment_approve_handler = approve
        self._voice_enrollment_reject_handler = reject
        self._voice_enrollment_test_handler = test_playback

    def set_onboarding_handlers(
        self,
        *,
        status: OnboardingStatusHandler,
        notify: OnboardingNotifyHandler | None = None,
    ) -> None:
        self._onboarding_status_handler = status
        self._onboarding_notify_handler = notify

    async def push_onboarding_step(self, payload: dict[str, Any]) -> None:
        await self.push_event(WebSocketEvent.onboarding_step_from_dict(payload))

    def health(self) -> tuple[bool, str, bool]:
        if self._thread is None or not self._thread.is_alive():
            return False, "not running", False
        return True, "ok", False

    def start(self, *, block: bool = False) -> None:
        if self._thread and self._thread.is_alive():
            return

        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )
        self._uvicorn = uvicorn.Server(config)

        def run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            if self.config.open_browser:
                url = f"http://{self.config.host}:{self.config.port}"
                threading.Timer(0.8, lambda: webbrowser.open(url)).start()
            self._loop.run_until_complete(self._uvicorn.serve())

        self._thread = threading.Thread(target=run, name="chat-ui-server", daemon=True)
        self._thread.start()
        if block:
            self._thread.join()

    async def stop(self) -> None:
        if self._uvicorn is not None:
            self._uvicorn.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)

    async def push_event(self, event: WebSocketEvent) -> None:
        await self._manager.broadcast(event)

    async def set_pipeline_step(
        self,
        step: PipelineStep,
        *,
        tool_name: str | None = None,
        message_id: str | None = None,
    ) -> None:
        self.pipeline_step = step
        await self.push_event(
            WebSocketEvent.pipeline_step(step, tool_name=tool_name, message_id=message_id)
        )

    async def set_voice_state(self, state: VoiceState) -> None:
        self.voice_state = state
        await self.push_event(WebSocketEvent.voice_state(state))

    async def set_mcp_servers(self, servers: list[McpServerStatus]) -> None:
        self.mcp_servers = servers
        await self.push_event(WebSocketEvent.mcp_status(servers))

    async def set_proactive_queue(self, items: list[ProactiveItem]) -> None:
        self.proactive_queue = items
        top = items[0] if items else None
        await self.push_event(WebSocketEvent.proactive_queue(len(items), top))

    async def push_approval_request(self, request: ApprovalRequestPayload) -> None:
        self.pending_approvals[request.event_id] = request
        await self.push_event(WebSocketEvent.approval_request(request))

    async def push_message(self, message: ChatMessage) -> None:
        await self.push_event(WebSocketEvent.message(message))

    async def set_component_health(self, components: list[ComponentHealthEntry]) -> None:
        self.component_health = components
        await self.push_event(WebSocketEvent.component_health(components))

    async def push_failure_prompt(self, request: FailurePromptPayload) -> None:
        self.pending_failures[request.event_id] = request
        await self.push_event(WebSocketEvent.failure_prompt(request))

    async def set_locked(self, locked: bool) -> None:
        self.locked = locked
        await self.push_event(WebSocketEvent.lock_state(locked))

    async def push_anomaly_alert(
        self,
        destination: str,
        detail: str,
        *,
        timestamp: str = "",
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        await self.push_event(WebSocketEvent.anomaly_alert(destination, detail, ts))

    async def set_lm_studio_wait(self, *, waiting: bool, message: str = "") -> None:
        self.lm_studio_waiting = waiting
        self.lm_studio_message = message
        await self.push_event(WebSocketEvent.lm_studio_wait(waiting=waiting, message=message))

    async def push_config_notify(self, message: str) -> None:
        await self.push_event(WebSocketEvent.config_notify(message))

    def _is_input_allowed(self) -> bool:
        if self.locked:
            return False
        if self._input_allowed is None:
            return True
        return self._input_allowed()

    async def _status_snapshot(self) -> WebSocketEvent:
        top = self.proactive_queue[0] if self.proactive_queue else None
        return WebSocketEvent.status_snapshot(
            pipeline_step=self.pipeline_step,
            voice_state=self.voice_state,
            mcp_servers=self.mcp_servers,
            proactive_count=len(self.proactive_queue),
            proactive_top=top,
            profile_name=self.config.profile_name,
            locked=self.locked,
            component_health=self.component_health,
            lm_studio_waiting=self.lm_studio_waiting,
            lm_studio_message=self.lm_studio_message,
        )

    async def _handle_user_input(self, text: str) -> None:
        if not self._is_input_allowed():
            locked_msg = self.session_store.add_message(
                "cobra",
                "Input is locked. Unlock C.O.B.R.A. to continue.",
            )
            await self.push_event(WebSocketEvent.message(locked_msg))
            return
        user_message = self.session_store.add_message("user", text)
        await self.push_event(WebSocketEvent.message(user_message))
        await self.set_pipeline_step(PipelineStep.REASONING)

        if self._input_handler is None:
            await self._default_input_handler(text)
            return

        result = self._input_handler(text)
        events = await result if asyncio.iscoroutine(result) else result
        for event in events:
            await self.push_event(event)
        await self.set_pipeline_step(PipelineStep.IDLE)

    async def _default_input_handler(self, text: str) -> None:
        """Stub until Brain wires process_input."""
        response = self.session_store.add_message(
            "cobra",
            "Brain is not connected yet. Your message was recorded locally.",
        )
        await self.push_event(WebSocketEvent.message(response))

    async def _resolve_approval(self, event_id: str, approved: bool) -> None:
        self.pending_approvals.pop(event_id, None)
        await self.push_event(WebSocketEvent.approval_resolved(event_id, approved))
        if self._approval_handler is None:
            return
        result = self._approval_handler(event_id, approved)
        if asyncio.iscoroutine(result):
            await result

    async def _resolve_failure(self, event_id: str, action: str) -> None:
        self.pending_failures.pop(event_id, None)
        await self.push_event(WebSocketEvent.failure_resolved(event_id, action))
        if self._failure_handler is None:
            return
        result = self._failure_handler(event_id, action)
        if asyncio.iscoroutine(result):
            await result

    async def _surface_proactive(self) -> None:
        if not self.proactive_queue:
            return
        item = self.proactive_queue.pop(0)
        await self.set_proactive_queue(self.proactive_queue)
        await self.push_event(WebSocketEvent.proactive_surfaced(item))
        if self._proactive_handler is None:
            return
        result = self._proactive_handler()
        if asyncio.iscoroutine(result):
            await result

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="C.O.B.R.A. Chat UI", docs_url=None, redoc_url=None)
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

        @app.get("/api/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/api/session/messages")
        async def session_messages() -> dict[str, Any]:
            return {
                "session_id": self.session_store.session_id,
                "messages": [message.to_dict() for message in self.session_store.messages],
            }

        @app.get("/api/session/{session_id}/messages")
        async def session_messages_by_id(session_id: str) -> dict[str, Any]:
            messages = self.session_store.load_session(session_id)
            if not messages:
                path = self.session_store.sessions_dir / f"{session_id}.json"
                if not path.exists():
                    raise HTTPException(status_code=404, detail="Session not found")
            return {
                "session_id": session_id,
                "messages": [message.to_dict() for message in messages],
            }

        @app.post("/api/session/{session_id}/activate")
        async def activate_session(session_id: str) -> dict[str, Any]:
            messages = self.session_store.switch_session(session_id)
            if not messages:
                path = self.session_store.sessions_dir / f"{session_id}.json"
                if not path.exists():
                    raise HTTPException(status_code=404, detail="Session not found")
            payload = {
                "type": "session_history",
                "payload": {
                    "session_id": session_id,
                    "messages": [message.to_dict() for message in messages],
                },
            }
            await self._manager.broadcast(
                WebSocketEvent(type="session_history", payload=payload["payload"])
            )
            return payload["payload"]

        @app.get("/api/wiki/pages")
        async def wiki_pages() -> dict[str, Any]:
            return {"pages": self.wiki.list_pages()}

        @app.get("/api/wiki/page/{page_name}")
        async def wiki_page(page_name: str) -> dict[str, str]:
            try:
                return self.wiki.read_page(page_name)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get("/api/wiki/index")
        async def wiki_index() -> dict[str, str]:
            return self.wiki.read_index()

        @app.get("/api/search")
        async def search(q: str = "") -> dict[str, Any]:
            results = self.search.search(q)
            return {"results": [result.to_dict() for result in results]}

        @app.post("/api/chat")
        async def chat(payload: ChatInput) -> dict[str, str]:
            if not self._is_input_allowed():
                raise HTTPException(status_code=403, detail="Input locked")
            await self._handle_user_input(payload.text.strip())
            return {"status": "accepted"}

        @app.post("/api/approval")
        async def approval(payload: ApprovalDecision) -> dict[str, str]:
            await self._resolve_approval(payload.event_id, payload.approved)
            return {"status": "resolved"}

        @app.post("/api/failure")
        async def failure(payload: FailureDecision) -> dict[str, str]:
            await self._resolve_failure(payload.event_id, payload.action)
            return {"status": "resolved"}

        @app.get("/api/wizard/status")
        async def wizard_status() -> dict[str, Any]:
            if self._wizard_status_handler is None:
                return {"needs_wizard": False}
            return self._wizard_status_handler()

        @app.post("/api/wizard/complete")
        async def wizard_complete(payload: dict[str, Any]) -> dict[str, Any]:
            if self._wizard_handler is None:
                raise HTTPException(status_code=503, detail="Wizard handler unavailable")
            result = self._wizard_handler(payload)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        @app.post("/api/wizard/rerun")
        async def wizard_rerun() -> dict[str, Any]:
            if self._wizard_status_handler is None:
                raise HTTPException(status_code=503, detail="Wizard unavailable")
            status_payload = self._wizard_status_handler()
            return {"status": "ready", **status_payload}

        @app.post("/api/lm-studio/cancel")
        async def lm_studio_cancel() -> dict[str, str]:
            if self._lm_studio_cancel_handler is None:
                raise HTTPException(status_code=503, detail="Cancel handler unavailable")
            result = self._lm_studio_cancel_handler()
            if asyncio.iscoroutine(result):
                await result
            return {"status": "cancelled"}

        @app.post("/api/proactive/tell-me-now")
        async def tell_me_now() -> dict[str, str]:
            await self._surface_proactive()
            return {"status": "surfaced"}

        @app.get("/api/seed/export")
        async def seed_export() -> dict[str, str]:
            if self._seed_export_handler is None:
                raise HTTPException(status_code=503, detail="Seed export unavailable")
            return self._seed_export_handler()

        @app.get("/api/seed/status")
        async def seed_status() -> dict[str, Any]:
            if self._seed_status_handler is None:
                raise HTTPException(status_code=503, detail="Seed status unavailable")
            return self._seed_status_handler()

        @app.get("/api/onboarding/status")
        async def onboarding_status() -> dict[str, Any]:
            if self._onboarding_status_handler is None:
                raise HTTPException(status_code=503, detail="Onboarding status unavailable")
            return self._onboarding_status_handler()

        @app.get("/api/voice/enrollment/status")
        async def voice_enrollment_status() -> dict[str, Any]:
            if self._voice_enrollment_status_handler is None:
                raise HTTPException(status_code=503, detail="Voice enrollment unavailable")
            return self._voice_enrollment_status_handler()

        @app.post("/api/voice/enrollment/sample")
        async def voice_enrollment_sample(payload: dict[str, Any]) -> dict[str, Any]:
            if self._voice_enrollment_sample_handler is None:
                raise HTTPException(status_code=503, detail="Voice enrollment unavailable")
            import base64

            raw = payload.get("audio_base64", "")
            if not raw:
                raise HTTPException(status_code=400, detail="audio_base64 required")
            try:
                wav_bytes = base64.b64decode(raw)
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Invalid audio_base64") from exc
            duration = payload.get("duration_seconds")
            result = self._voice_enrollment_sample_handler(
                wav_bytes,
                float(duration) if duration is not None else None,
            )
            if self._onboarding_notify_handler:
                self._onboarding_notify_handler()
            return result

        @app.post("/api/voice/enrollment/train")
        async def voice_enrollment_train() -> dict[str, Any]:
            if self._voice_enrollment_train_handler is None:
                raise HTTPException(status_code=503, detail="Voice enrollment unavailable")
            result = self._voice_enrollment_train_handler()
            if asyncio.iscoroutine(result):
                result = await result
            if self._onboarding_notify_handler:
                self._onboarding_notify_handler()
            return result

        @app.post("/api/voice/enrollment/approve")
        async def voice_enrollment_approve() -> dict[str, Any]:
            if self._voice_enrollment_approve_handler is None:
                raise HTTPException(status_code=503, detail="Voice enrollment unavailable")
            result = self._voice_enrollment_approve_handler()
            if asyncio.iscoroutine(result):
                result = await result
            if self._onboarding_notify_handler:
                self._onboarding_notify_handler()
            return result

        @app.post("/api/voice/enrollment/reject")
        async def voice_enrollment_reject() -> dict[str, Any]:
            if self._voice_enrollment_reject_handler is None:
                raise HTTPException(status_code=503, detail="Voice enrollment unavailable")
            result = self._voice_enrollment_reject_handler()
            if asyncio.iscoroutine(result):
                result = await result
            if self._onboarding_notify_handler:
                self._onboarding_notify_handler()
            return result

        @app.post("/api/voice/enrollment/test-playback")
        async def voice_enrollment_test() -> dict[str, Any]:
            if self._voice_enrollment_test_handler is None:
                raise HTTPException(status_code=503, detail="Voice enrollment unavailable")
            result = self._voice_enrollment_test_handler()
            if asyncio.iscoroutine(result):
                result = await result
            return result

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await self._manager.connect(websocket)
            try:
                await websocket.send_json((await self._status_snapshot()).to_dict())
                await websocket.send_json(
                    {
                        "type": "session_history",
                        "payload": {
                            "messages": [
                                message.to_dict()
                                for message in self.session_store.messages
                            ]
                        },
                    }
                )
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self._manager.disconnect(websocket)

        return app
