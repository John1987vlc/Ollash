import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

# Import blueprints to be tested
from frontend.blueprints import (  # Import the new registration function
    auto_agent_bp, benchmark_bp, common_bp, register_blueprints)
from frontend.services.chat_session_manager import \
    ChatSessionManager  # Import the actual class for type hinting (not for direct patching here)

# Import the chat_bp module directly (not the Blueprint object from __init__.py)
# This is needed to access module-level globals like _session_manager
chat_bp_module = importlib.import_module("frontend.blueprints.chat_bp")
chat_bp = chat_bp_module.chat_bp  # The Blueprint object


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create and configure a new app instance for each test."""
    # Create a mock app
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent
    template_path = project_root / "frontend" / "templates"
    app = Flask(__name__, template_folder=str(template_path))
    app.config["TESTING"] = True
    app.config["OLLASH_ROOT_DIR"] = tmp_path

    # Mock the event publisher and bridge
    mock_event_publisher = MagicMock()
    mock_chat_event_bridge = MagicMock()
    mock_alert_manager = MagicMock()  # Mock alert manager
    mock_logger = MagicMock()  # Mock logger
    app.config["logger"] = mock_logger  # Add mock logger to app.config

    # Create a mock session manager instance that will be injected into chat_bp
    app.mock_session_manager_instance = MagicMock(spec=ChatSessionManager)

    # Initialize all blueprints using the centralized register_blueprints function
    # Patch the actual init_app functions within the blueprint modules themselves
    # before calling register_blueprints. This ensures that the centralized
    # function is tested, but the individual init_app logic is mocked.
    for bp_module in [common_bp, benchmark_bp, auto_agent_bp]:
        if hasattr(bp_module, "init_app"):
            monkeypatch.setattr(bp_module, "init_app", lambda *args, **kwargs: None)

    register_blueprints(
        app=app,
        ollash_root_dir=tmp_path,
        event_publisher=mock_event_publisher,
        chat_event_bridge=mock_chat_event_bridge,
        alert_manager=mock_alert_manager,
        # chat_bp is NOT passed as a keyword argument to register_blueprints
    )

    # AFTER register_blueprints runs and init_chat sets chat_bp._session_manager
    # We explicitly override it with our mock to ensure it's used in tests.
    # The _session_manager is a global in the chat_bp module, not an attribute of the chat_bp Blueprint object.
    monkeypatch.setattr(
        chat_bp_module, "_session_manager", app.mock_session_manager_instance
    )

    with app.app_context():
        # Patch external dependencies for all tests in this file
        with patch("backend.agents.auto_agent.AutoAgent"), patch(
            "backend.agents.auto_benchmarker.ModelBenchmarker"
        ), patch("frontend.services.chat_session_manager.DefaultAgent"):
            yield app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestCommonBlueprint:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.content_type

    def test_index_has_agent_cards(self, client):
        resp = client.get("/")
        assert b'class="agent-card"' in resp.data


class TestChatBlueprint:
    def test_chat_requires_message(self, client):
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 400

    def test_chat_creates_session(self, client, app):
        mock_mgr = app.mock_session_manager_instance  # Use the mock set by the fixture
        mock_session_id = "new-dynamic-session-id"
        mock_mgr.create_session.return_value = mock_session_id
        mock_mgr.get_session.return_value = None  # No existing session

        resp = client.post(
            "/api/chat", json={"message": "hello", "agent_type": "default"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["session_id"] == mock_session_id
        # create_session is called with positional args (project_path, agent_type)
        mock_mgr.create_session.assert_called_once_with(None, "default")

    def test_chat_passes_agent_type(self, client, app):
        mock_mgr = app.mock_session_manager_instance  # Use the mock set by the fixture
        mock_session_id = "new-dynamic-session-id-code"
        mock_mgr.create_session.return_value = mock_session_id
        mock_mgr.get_session.return_value = None  # No existing session

        client.post("/api/chat", json={"message": "hi", "agent_type": "code"})
        mock_mgr.create_session.assert_called_once_with(None, "code")

    def test_chat_stream_404_unknown_session(self, client, app):
        # Configure mock to return None for unknown session
        app.mock_session_manager_instance.get_session.return_value = None
        resp = client.get("/api/chat/stream/unknown-session-id")
        assert resp.status_code == 404

    def test_chat_max_sessions_error(self, client, app):
        mock_mgr = app.mock_session_manager_instance  # Use the mock set by the fixture
        # Simulate session limit reached by raising RuntimeError from create_session
        mock_mgr.create_session.side_effect = RuntimeError("Session limit reached")

        resp = client.post("/api/chat", json={"message": "test"})
        assert resp.status_code == 429  # Too Many Requests
        assert "Session limit reached" in resp.get_json()["message"]


class TestBenchmarkBlueprint:
    def test_models_endpoint(self, client, monkeypatch):
        # This test now needs to patch requests inside the blueprint's scope
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "models": [{"name": "test-model", "size": 1000}]
            }
            mock_get.return_value.raise_for_status = lambda: None

            resp = client.get("/api/benchmark/models")
            assert resp.status_code == 200
            data = resp.get_json()
            # Response structure is {"status": "ok", "models": [{"name": "test-model", ...}]}
            assert data["status"] == "ok"
            assert any(m["name"] == "test-model" for m in data["models"])

    def test_models_connection_error(self, client, monkeypatch):
        import requests

        with patch("requests.get", side_effect=requests.ConnectionError()):
            resp = client.get("/api/benchmark/models")
            # ConnectionError returns 503, not 500
            assert resp.status_code == 503
            # Response structure uses "message" key
            assert "message" in resp.get_json()

    def test_start_requires_models(self, client):
        resp = client.post("/api/benchmark/start", json={})
        assert resp.status_code == 400

    def test_results_list(self, client, tmp_path):
        # Create a fake result file
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        fake_result = log_dir / "auto_benchmark_results_20260101_120000.json"
        fake_result.write_text(json.dumps([{"model": "test"}]))

        resp = client.get("/api/benchmark/results")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert len(data["results"]) >= 1

    def test_results_get_specific(self, client, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        fake_result = log_dir / "auto_benchmark_results_20260101_120000.json"
        fake_result.write_text(json.dumps([{"model": "test", "score": 8}]))

        resp = client.get(
            "/api/benchmark/results/auto_benchmark_results_20260101_120000.json"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["data"][0]["model"] == "test"

    def test_results_invalid_filename(self, client):
        resp = client.get("/api/benchmark/results/malicious_file.json")
        assert resp.status_code == 400
