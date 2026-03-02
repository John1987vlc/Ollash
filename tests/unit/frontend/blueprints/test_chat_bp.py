"""
Chat router unit tests — migrated from Flask blueprint tests.

Changes from Flask version:
- Flask `app.test_client()` → starlette `TestClient`
- `app.config[...]` → `app.state.*` overrides
- `with app.app_context():` → removed (not needed in FastAPI)
- `response.get_json()` → `response.json()`
- `response.data` → `response.content`
"""

import pytest
from unittest.mock import MagicMock
from starlette.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def mock_manager():
    """Mock ChatSessionManager."""
    mgr = MagicMock()
    mgr.get_session.return_value = None
    mgr.create_session.return_value = "new-s-id"
    return mgr


@pytest.fixture
def app(mock_manager, tmp_path):
    _app = create_app()
    # Override app.state services with mocks
    _app.state.event_publisher = MagicMock()
    _app.state.chat_event_bridge = MagicMock()
    _app.state.automation_manager = MagicMock()
    _app.state.notification_manager = MagicMock()
    _app.state.alert_manager = MagicMock()
    _app.state.ollash_root_dir = tmp_path

    # Inject mock session manager into the chat router module
    import backend.api.routers.chat_router as chat_mod

    chat_mod._session_manager = mock_manager

    yield _app

    # Cleanup
    chat_mod._session_manager = None


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.unit
class TestChatRouter:
    """Test suite for the FastAPI chat router."""

    def test_send_chat_creates_session_if_needed(self, client, mock_manager):
        mock_manager.get_session.return_value = None
        mock_manager.create_session.return_value = "new-s-id"

        response = client.post("/api/chat", json={"message": "Hello"})

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "new-s-id"
        mock_manager.send_message.assert_called_once_with("new-s-id", "Hello")

    def test_send_chat_uses_existing_session(self, client, mock_manager):
        existing_session = MagicMock()
        mock_manager.get_session.return_value = existing_session

        response = client.post("/api/chat", json={"message": "Msg 2", "session_id": "s-123"})

        assert response.status_code == 200
        mock_manager.send_message.assert_called_once_with("s-123", "Msg 2")

    def test_stream_chat_not_found(self, client, mock_manager):
        mock_manager.get_session.return_value = None
        response = client.get("/api/chat/stream/invalid")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_sessions(self, client, mock_manager):
        mock_manager.list_sessions.return_value = [{"id": "s1", "model": "default"}]
        response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        assert len(response.json()["sessions"]) == 1
