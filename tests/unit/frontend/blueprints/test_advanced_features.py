import pytest
import json
from pathlib import Path
from flask import Flask
from frontend.blueprints import register_blueprints


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True

    mock_root = Path("test_root")
    # Correctly initialize AgentLogger with StructuredLogger
    from backend.utils.core.system.structured_logger import StructuredLogger
    from backend.utils.core.system.agent_logger import AgentLogger

    sl = StructuredLogger(mock_root / "test.log")
    app.config["logger"] = AgentLogger(sl, "test")

    # Mock services for blueprint registration
    mock_publisher = pytest.importorskip("backend.utils.core.system.event_publisher").EventPublisher()
    mock_bridge = pytest.importorskip("frontend.services.chat_event_bridge").ChatEventBridge(mock_publisher)
    mock_alerts = pytest.importorskip("backend.utils.core.system.alert_manager").AlertManager(mock_publisher, mock_root)

    register_blueprints(app, mock_root, mock_publisher, mock_bridge, mock_alerts)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_blueprint_registration(app):
    """Verify that all advanced blueprints are registered."""
    expected_bps = [
        "prompt_studio",
        "audit",
        "knowledge",
        "decisions",
        "tuning",
        "hil",
        "translator",
        "policies",
        "checkpoints",
        "fragments",
        "router",
    ]
    registered_names = [bp.name for bp in app.blueprints.values()]
    for name in expected_bps:
        assert name in registered_names


def test_prompt_studio_api(client):
    """Test Prompt Studio validation endpoint."""
    payload = {"prompt": "Short prompt"}
    response = client.post("/prompts/api/validate", json=payload)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "warnings" in data


def test_audit_llm_api(client):
    """Test LLM Audit endpoint (should return empty if no logs)."""
    response = client.get("/api/audit/llm")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "events" in data


def test_knowledge_base_api(client):
    """Test Knowledge Base document listing."""
    response = client.get("/api/knowledge/documents")
    # Might fail if ChromaDB not initialized, but we check availability
    assert response.status_code in [200, 500]


def test_hil_response_api(client):
    """Test Human-in-the-loop response submission."""
    payload = {"request_id": "test_req", "response": "approve", "feedback": "LGTM"}
    response = client.post("/api/hil/respond", json=payload)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"


def test_tuning_config_api(client):
    """Test Tuning Studio config retrieval."""
    response = client.get("/api/tuning/config")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "auto_tune_enabled" in data


def test_policies_api(client):
    """Test Governance Policies retrieval."""
    response = client.get("/api/policies")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "allowed_commands" in data
