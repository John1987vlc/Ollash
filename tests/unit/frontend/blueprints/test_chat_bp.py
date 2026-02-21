import pytest
from unittest.mock import MagicMock
import sys
from flask import Flask

# Import the blueprint object
from frontend.blueprints.chat_bp import chat_bp, init_app


@pytest.fixture
def mock_manager_instance():
    """Create a mock instance of ChatSessionManager."""
    return MagicMock()


@pytest.fixture
def app(mock_manager_instance, monkeypatch):
    """Create app and ensure the blueprint module uses the mocked manager instance."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": "/tmp/ollash", "SECRET_KEY": "test_secret"})

    # RELIABLE PATCHING: Access the module through sys.modules to avoid Blueprint object shadowing
    target_module = sys.modules["frontend.blueprints.chat_bp"]

    # Inject our mock manager instance into the module's global state
    monkeypatch.setattr(target_module, "_session_manager", mock_manager_instance)
    # Also mock render_template in the same module namespace
    monkeypatch.setattr(target_module, "render_template", MagicMock(return_value="<html></html>"))

    # Call init_app - it will set the global, but our monkeypatch should intercept/override it
    init_app(app, MagicMock())
    # Force set it one last time to be absolutely sure
    setattr(target_module, "_session_manager", mock_manager_instance)

    app.register_blueprint(chat_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestChatBlueprint:
    """Test suite for Chat Blueprint interactive routes with absolute module isolation."""

    def test_chat_page_renders(self, client):
        response = client.get("/chat")
        assert response.status_code == 200

    def test_send_chat_creates_session_if_needed(self, client, mock_manager_instance):
        mock_manager_instance.get_session.return_value = None
        mock_manager_instance.create_session.return_value = "new-s-id"

        response = client.post("/api/chat", json={"message": "Hello", "agent_type": "orchestrator"})

        assert response.status_code == 200
        assert response.get_json()["session_id"] == "new-s-id"
        mock_manager_instance.send_message.assert_called_once_with("new-s-id", "Hello")

    def test_send_chat_uses_existing_session(self, client, mock_manager_instance):
        mock_manager_instance.get_session.return_value = MagicMock()

        response = client.post("/api/chat", json={"message": "Msg 2", "session_id": "s-123"})

        assert response.status_code == 200
        mock_manager_instance.send_message.assert_called_once_with("s-123", "Msg 2")

    def test_send_chat_empty_message_error(self, client):
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 400

    def test_send_chat_rate_limit_handling(self, client, mock_manager_instance):
        mock_manager_instance.get_session.return_value = MagicMock()
        mock_manager_instance.send_message.side_effect = RuntimeError("Rate limit")

        response = client.post("/api/chat", json={"message": "test", "session_id": "s1"})
        assert response.status_code == 429

    def test_stream_chat_success(self, client, mock_manager_instance):
        mock_session = MagicMock()
        mock_session.bridge.iter_events.return_value = iter(["data: ping\n\n"])
        mock_manager_instance.get_session.return_value = mock_session

        response = client.get("/api/chat/stream/s1")
        assert response.status_code == 200
        assert b"data: ping" in response.data

    def test_stream_chat_not_found(self, client, mock_manager_instance):
        mock_manager_instance.get_session.return_value = None
        response = client.get("/api/chat/stream/invalid")
        assert response.status_code == 404
