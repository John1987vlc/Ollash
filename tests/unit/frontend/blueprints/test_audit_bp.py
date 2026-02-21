import pytest
from unittest.mock import MagicMock, patch
import json
import sys
from flask import Flask

# Import the blueprint object
from frontend.blueprints.audit_bp import audit_bp


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a Flask app for testing audit endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True})

    # Access the module directly to bypass Blueprint object name shadowing
    target_module = sys.modules["frontend.blueprints.audit_bp"]

    # Mock the container and its methods
    mock_container = MagicMock()
    mock_container.core.ollash_root_dir.return_value = tmp_path

    # Inject the mock container directly into the module's globals
    monkeypatch.setattr(target_module, "main_container", mock_container)

    app.register_blueprint(audit_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def log_file(tmp_path):
    """Path to the test log file."""
    return tmp_path / "ollash.log"


class TestAuditBlueprint:
    """Test suite for Audit and Logging endpoints with total module-level isolation."""

    def test_audit_page_renders(self, client):
        # Mock render_template in the module namespace
        target_module = sys.modules["frontend.blueprints.audit_bp"]
        with patch.object(target_module, "render_template", return_value="<html></html>"):
            response = client.get("/audit")
            assert response.status_code == 200

    def test_get_llm_audit_success(self, client, log_file):
        # Create a log file with various types of events
        events = [
            {"event_type": "llm_request", "model": "qwen3", "msg": "req1"},
            {"event_type": "llm_response", "tokens": 50, "msg": "res1"},
            {"event_type": "system_init", "status": "ok"},
            "INVALID JSON LINE",
            {"type": "llm_request", "msg": "req2"},
        ]

        with open(log_file, "w", encoding="utf-8") as f:
            for e in events:
                if isinstance(e, dict):
                    f.write(json.dumps(e) + "\n")
                else:
                    f.write(e + "\n")

        response = client.get("/api/audit/llm?limit=10")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["events"]) == 3
        # Check reverse order (newest first)
        assert data["events"][0]["msg"] == "req2"
        assert data["events"][2]["msg"] == "req1"

    def test_get_llm_audit_no_file(self, client):
        response = client.get("/api/audit/llm")
        assert response.status_code == 200
        assert response.get_json()["events"] == []

    def test_get_llm_audit_limit(self, client, log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            for i in range(10):
                f.write(json.dumps({"event_type": "llm_request", "id": i}) + "\n")

        response = client.get("/api/audit/llm?limit=5")
        assert len(response.get_json()["events"]) == 5

    def test_download_logs_success(self, client, log_file):
        log_file.write_text("dummy log content")

        target_module = sys.modules["frontend.blueprints.audit_bp"]
        with patch.object(target_module, "send_file") as mock_send:
            mock_send.return_value = "file_sent"
            response = client.get("/api/audit/download/llm_logs.json")

            assert response.data.decode() == "file_sent"
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            assert args[0] == log_file
            assert kwargs["as_attachment"] is True

    def test_download_logs_not_found(self, client):
        response = client.get("/api/audit/download/llm_logs.json")
        assert response.status_code == 404
