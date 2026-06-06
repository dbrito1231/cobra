"""Tests for the Chat UI component."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chat_ui.config import ChatUIConfig
from chat_ui.models import (
    ApprovalRequestPayload,
    McpServerStatus,
    McpStatus,
    PipelineStep,
    ProactiveItem,
    VoiceState,
    WebSocketEvent,
)
from chat_ui.search import ConversationSearch
from chat_ui.server import ChatUIServer
from chat_ui.session_store import SessionStore
from chat_ui.wiki import WikiService


@pytest.fixture
def tmp_config(tmp_path: Path) -> ChatUIConfig:
    wiki_dir = tmp_path / "wiki"
    sessions_dir = tmp_path / "sessions"
    wiki_dir.mkdir()
    sessions_dir.mkdir()
    return ChatUIConfig(
        host="127.0.0.1",
        port=8765,
        wiki_dir=wiki_dir,
        sessions_dir=sessions_dir,
        profile_name="Test",
        open_browser=False,
    )


@pytest.fixture
def server(tmp_config: ChatUIConfig) -> ChatUIServer:
    return ChatUIServer(tmp_config)


@pytest.fixture
def client(server: ChatUIServer) -> TestClient:
    return TestClient(server.app)


class TestWikiService:
    def test_ensure_index_creates_default(self, tmp_config: ChatUIConfig) -> None:
        wiki = WikiService(tmp_config.wiki_dir)
        wiki.ensure_index()
        index = wiki.read_index()
        assert "C.O.B.R.A. Wiki" in index["content"]

    def test_list_and_read_pages(self, tmp_config: ChatUIConfig) -> None:
        wiki = WikiService(tmp_config.wiki_dir)
        wiki.ensure_index()
        (tmp_config.wiki_dir / "topics.md").write_text("# Topics\n\nTopic list.")
        pages = wiki.list_pages()
        assert any(page["name"] == "topics" for page in pages)
        page = wiki.read_page("topics")
        assert page["title"] == "Topics"


class TestSessionStore:
    def test_add_and_persist_messages(self, tmp_config: ChatUIConfig) -> None:
        store = SessionStore(tmp_config.sessions_dir)
        store.add_message("user", "Hello")
        store.add_message("cobra", "Hi there")
        assert len(store.messages) == 2
        reloaded = SessionStore(tmp_config.sessions_dir)
        assert len(reloaded.messages) == 2


class TestConversationSearch:
    def test_search_finds_matching_messages(self, tmp_config: ChatUIConfig) -> None:
        store = SessionStore(tmp_config.sessions_dir)
        store.add_message("user", "Remember the quantum project deadline")
        search = ConversationSearch(store)
        results = search.search("quantum")
        assert len(results) == 1
        assert "quantum" in results[0].excerpt.lower()


class TestWebSocketEvents:
    def test_pipeline_step_labels(self) -> None:
        event = WebSocketEvent.pipeline_step(
            PipelineStep.TOOL_EXECUTION, tool_name="web_search"
        )
        assert event.payload["label"] == "Running tool: web_search"

    def test_approval_from_tools_event(self) -> None:
        payload = ApprovalRequestPayload.from_tools_approval(
            {
                "event_id": "abc",
                "explanation": "Needs approval",
                "action_type": "code_execution",
                "tool_call": {
                    "tool_name": "code_execution",
                    "params": {"path": "/tmp", "query": "test"},
                },
                "code_preview": "print('hello')",
            }
        )
        assert "code_execution" in payload.what
        assert payload.code_preview == "print('hello')"
        assert "path:" in payload.data_summary
        assert "/tmp" not in payload.data_summary or "path: /tmp" in payload.data_summary

    def test_approval_sanitizes_email(self) -> None:
        payload = ApprovalRequestPayload.from_tools_approval(
            {
                "event_id": "x",
                "tool_call": {
                    "tool_name": "web_search",
                    "params": {"query": "contact user@example.com"},
                },
            }
        )
        assert "[email]" in payload.data_summary


class TestChatUIServer:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_index_returns_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_wiki_index_api(self, client: TestClient) -> None:
        response = client.get("/api/wiki/index")
        assert response.status_code == 200
        assert "content" in response.json()

    def test_chat_message_flow(self, client: TestClient) -> None:
        response = client.post("/api/chat", json={"text": "Hello C.O.B.R.A."})
        assert response.status_code == 200
        messages = client.get("/api/session/messages").json()["messages"]
        assert len(messages) == 2
        assert messages[0]["sender"] == "user"
        assert messages[1]["sender"] == "cobra"

    def test_search_api(self, client: TestClient) -> None:
        client.post("/api/chat", json={"text": "Find the mars colony plan"})
        response = client.get("/api/search", params={"q": "mars colony"})
        results = response.json()["results"]
        assert len(results) >= 1

    def test_load_session_by_id(self, client: TestClient, server: ChatUIServer) -> None:
        client.post("/api/chat", json={"text": "Session marker alpha"})
        session_id = server.session_store.session_id
        response = client.get(f"/api/session/{session_id}/messages")
        assert response.status_code == 200
        assert len(response.json()["messages"]) == 2

    def test_activate_session(self, client: TestClient, server: ChatUIServer) -> None:
        client.post("/api/chat", json={"text": "First session"})
        archived_id = server.session_store.session_id
        server.session_store.new_session()
        client.post("/api/chat", json={"text": "Second session"})
        response = client.post(f"/api/session/{archived_id}/activate")
        assert response.status_code == 200
        assert response.json()["session_id"] == archived_id
        assert len(response.json()["messages"]) == 2

    def test_approval_endpoint(self, client: TestClient) -> None:
        response = client.post(
            "/api/approval",
            json={"event_id": "test-id", "approved": True},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_push_events(self, server: ChatUIServer) -> None:
        await server.set_voice_state(VoiceState.LISTENING)
        assert server.voice_state == VoiceState.LISTENING
        await server.set_pipeline_step(PipelineStep.REASONING)
        assert server.pipeline_step == PipelineStep.REASONING
        await server.set_mcp_servers(
            [McpServerStatus(name="github", status=McpStatus.ONLINE)]
        )
        assert len(server.mcp_servers) == 1

    @pytest.mark.asyncio
    async def test_proactive_queue(self, server: ChatUIServer, client: TestClient) -> None:
        await server.set_proactive_queue(
            [ProactiveItem(id="1", preview="Check calendar", priority=1)]
        )
        response = client.post("/api/proactive/tell-me-now")
        assert response.status_code == 200
        assert len(server.proactive_queue) == 0

    def test_websocket_receives_snapshot(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "status_snapshot"
            history = websocket.receive_json()
            assert history["type"] == "session_history"

    def test_config_from_dict(self) -> None:
        config = ChatUIConfig.from_config_dict(
            {
                "ui": {"port": 9000, "host": "127.0.0.1"},
                "active_profile": "default",
                "profiles": {
                    "default": {
                        "name": "Work",
                        "storage": {"wiki_dir": "~/custom/wiki"},
                    }
                },
            }
        )
        assert config.port == 9000
        assert config.profile_name == "Work"
