"""FastAPI server, WebSocket hub, and integration hooks for Brain/Voice."""

from __future__ import annotations

import asyncio
import threading
import webbrowser
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Union

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chat_ui.config import ChatUIConfig
from chat_ui.models import (
    ApprovalRequestPayload,
    ChatMessage,
    McpServerStatus,
    McpStatus,
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

        self._manager = ConnectionManager()
        self._input_handler: InputHandler | None = None
        self._approval_handler: ApprovalHandler | None = None
        self._proactive_handler: ProactiveHandler | None = None
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

    async def _status_snapshot(self) -> WebSocketEvent:
        top = self.proactive_queue[0] if self.proactive_queue else None
        return WebSocketEvent.status_snapshot(
            pipeline_step=self.pipeline_step,
            voice_state=self.voice_state,
            mcp_servers=self.mcp_servers,
            proactive_count=len(self.proactive_queue),
            proactive_top=top,
            profile_name=self.config.profile_name,
        )

    async def _handle_user_input(self, text: str) -> None:
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
            await self._handle_user_input(payload.text.strip())
            return {"status": "accepted"}

        @app.post("/api/approval")
        async def approval(payload: ApprovalDecision) -> dict[str, str]:
            await self._resolve_approval(payload.event_id, payload.approved)
            return {"status": "resolved"}

        @app.post("/api/proactive/tell-me-now")
        async def tell_me_now() -> dict[str, str]:
            await self._surface_proactive()
            return {"status": "surfaced"}

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
