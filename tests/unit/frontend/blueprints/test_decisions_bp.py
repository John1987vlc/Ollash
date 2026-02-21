import pytest
from unittest.mock import MagicMock, patch
import sys
from flask import Flask

# Import the blueprint object
from frontend.blueprints.decisions_bp import decisions_bp


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a Flask app for testing decision endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True})

    # Access the module directly to patch main_container
    target_module = sys.modules["frontend.blueprints.decisions_bp"]

    # Mock the container
    mock_container = MagicMock()
    mock_container.core.ollash_root_dir.return_value = tmp_path
    monkeypatch.setattr(target_module, "main_container", mock_container)

    app.register_blueprint(decisions_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestDecisionsBlueprint:
    """Test suite for Agent Decisions tracking endpoints with local import handling."""

    @patch("backend.utils.core.memory.episodic_memory.EpisodicMemory")
    @patch("backend.utils.core.system.agent_logger.AgentLogger")
    @patch("backend.utils.core.system.structured_logger.StructuredLogger")
    def test_get_decisions_success(self, mock_sl, mock_al, mock_mem_cls, client):
        # Setup mock memory
        mock_memory = mock_mem_cls.return_value
        mock_dec = MagicMock()
        mock_dec.to_dict.return_value = {"id": 1, "decision": "Use Python"}
        mock_memory.recall_decisions.return_value = [mock_dec]

        response = client.get("/api/decisions?limit=5")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["decision"] == "Use Python"
        mock_memory.recall_decisions.assert_called_with(max_results=5)

    @patch("backend.utils.core.memory.episodic_memory.EpisodicMemory")
    @patch("backend.utils.core.system.agent_logger.AgentLogger")
    @patch("backend.utils.core.system.structured_logger.StructuredLogger")
    def test_get_session_decisions_success(self, mock_sl, mock_al, mock_mem_cls, client):
        mock_memory = mock_mem_cls.return_value
        mock_memory._db_path = "dummy.db"

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_row = {"id": 1, "session_id": "s123", "decision": "test"}
            mock_conn.execute.return_value.fetchall.return_value = [mock_row]

            response = client.get("/api/decisions/session/s123")

            assert response.status_code == 200
            data = response.get_json()
            assert len(data["decisions"]) == 1
            assert data["decisions"][0]["session_id"] == "s123"

    @patch("backend.utils.core.memory.episodic_memory.EpisodicMemory")
    def test_get_decisions_default_limit(self, mock_mem_cls, client):
        mock_memory = mock_mem_cls.return_value
        mock_memory.recall_decisions.return_value = []

        # We need to also patch the loggers here if they are imported locally
        with (
            patch("backend.utils.core.system.agent_logger.AgentLogger"),
            patch("backend.utils.core.system.structured_logger.StructuredLogger"),
        ):
            response = client.get("/api/decisions")
            assert response.status_code == 200
            mock_memory.recall_decisions.assert_called_with(max_results=20)

    @patch("backend.utils.core.memory.episodic_memory.EpisodicMemory")
    def test_get_session_decisions_empty(self, mock_mem_cls, client):
        mock_memory = mock_mem_cls.return_value
        mock_memory._db_path = "dummy.db"

        with (
            patch("backend.utils.core.system.agent_logger.AgentLogger"),
            patch("backend.utils.core.system.structured_logger.StructuredLogger"),
            patch("sqlite3.connect") as mock_connect,
        ):
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            response = client.get("/api/decisions/session/empty")
            assert response.status_code == 200
            assert response.get_json()["decisions"] == []
