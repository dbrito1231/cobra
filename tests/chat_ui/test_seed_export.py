"""Tests for seed export and status HTTP endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chat_ui.config import ChatUIConfig
from chat_ui.server import ChatUIServer


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
def client(tmp_config: ChatUIConfig) -> TestClient:
    server = ChatUIServer(tmp_config)
    server.set_seed_export_handler(
        lambda: {
            "you_md": "# You\n\n## Communication Style\nDirect.",
            "seed_state": '{"current_stage": "communication"}',
            "you_history_md": "# You Page Version History\n",
        }
    )
    server.set_seed_status_handler(
        lambda: {
            "mvp_complete": False,
            "profile_complete": False,
            "optional_remaining": True,
            "current_stage": "communication",
            "phase": "asking",
            "resume_label": "Communication Style — resume",
        }
    )
    return TestClient(server.app)


class TestSeedExportApi:
    def test_export_endpoint(self, client: TestClient) -> None:
        response = client.get("/api/seed/export")
        assert response.status_code == 200
        payload = response.json()
        assert "you_md" in payload
        assert "seed_state" in payload
        assert "you_history_md" in payload

    def test_status_endpoint(self, client: TestClient) -> None:
        response = client.get("/api/seed/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["mvp_complete"] is False
        assert payload["optional_remaining"] is True
