"""Unit tests for the Ollash Web UI (frontend/)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with mocked dependencies."""
    # Create a .env file with minimal necessary config for the web UI to start
    (tmp_path / ".env").write_text(f"""
OLLAMA_URL=http://localhost:11434
DEFAULT_MODEL=test-model
LLM_MODELS_JSON='{{"models": {{"default": "test-model", "coder": "test-coder"}}}}'
TOOL_SETTINGS_JSON='{{"default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json"}}'
""")

    # Create prompts directory and a dummy prompt file
    prompts_dir = tmp_path / "prompts" / "orchestrator"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "default_orchestrator.json").write_text(json.dumps({
        "prompt": "You are a test agent.",
        "tools": ["plan_actions"]
    }))
    
    # Create other prompt dirs needed by DefaultAgent
    for domain in ["code", "network", "system", "cybersecurity"]:
        d = tmp_path / "prompts" / domain
        d.mkdir(parents=True, exist_ok=True)
        fname = "default_agent.json" if domain == "code" else f"default_{domain}_agent.json"
        (d / fname).write_text(json.dumps({"prompt": f"You are a {domain} agent.", "tools": []}))


    # Create logs dir
    (tmp_path / "logs").mkdir()

    # Patch modules that would make external calls or are heavy to instantiate
    with patch("frontend.blueprints.auto_agent_bp.AutoAgent"), \
         patch("frontend.blueprints.benchmark_bp.ModelBenchmarker"), \
         patch("frontend.services.chat_session_manager.DefaultAgent"):
        from frontend.app import create_app
        flask_app = create_app(ollash_root_dir=tmp_path)
        flask_app.config["TESTING"] = True
        yield flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ==================== Common Blueprint ====================

class TestCommonBlueprint:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Ollash" in resp.data

    def test_index_has_chat_tab(self, client):
        resp = client.get("/")
        assert b'data-view="chat"' in resp.data

    def test_index_has_benchmark_tab(self, client):
        resp = client.get("/")
        assert b'data-view="benchmark"' in resp.data

    def test_index_has_agent_cards(self, client):
        resp = client.get("/")
        assert b'data-agent="code"' in resp.data
        assert b'data-agent="network"' in resp.data
        assert b'data-agent="system"' in resp.data
        assert b'data-agent="cybersecurity"' in resp.data
        assert b'data-agent="orchestrator"' in resp.data


# ==================== Chat Blueprint ====================

class TestChatBlueprint:
    def test_chat_requires_message(self, client):
        resp = client.post("/api/chat",
                           data=json.dumps({"message": ""}),
                           content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["status"] == "error"

    def test_chat_creates_session(self, client):
        with patch("frontend.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            mock_mgr.create_session.return_value = "abc123"

            resp = client.post("/api/chat",
                               data=json.dumps({"message": "hello"}),
                               content_type="application/json")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "started"
            assert data["session_id"] == "abc123"
            mock_mgr.create_session.assert_called_once()

    def test_chat_passes_agent_type(self, client):
        with patch("frontend.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            mock_mgr.create_session.return_value = "abc123"

            resp = client.post("/api/chat",
                               data=json.dumps({"message": "scan ports", "agent_type": "cybersecurity"}),
                               content_type="application/json")
            assert resp.status_code == 200
            mock_mgr.create_session.assert_called_once_with(None, "cybersecurity")

    def test_chat_stream_404_unknown_session(self, client):
        with patch("frontend.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            resp = client.get("/api/chat/stream/nonexistent")
            assert resp.status_code == 404

    def test_chat_max_sessions_error(self, client):
        with patch("frontend.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            mock_mgr.create_session.side_effect = RuntimeError("Maximum concurrent sessions (5) reached.")

            resp = client.post("/api/chat",
                               data=json.dumps({"message": "hello"}),
                               content_type="application/json")
            assert resp.status_code == 429


# ==================== Benchmark Blueprint ====================

class TestBenchmarkBlueprint:
    def test_models_endpoint(self, client):
        with patch("frontend.blueprints.benchmark_bp.requests.get") as mock_get, \
             patch("frontend.blueprints.benchmark_bp.ModelBenchmarker") as MockBench:
            MockBench.format_size.side_effect = lambda b: f"{b / 1e9:.1f} GB"

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "models": [
                    {"name": "model-a", "size": 1_000_000_000},
                    {"name": "model-b", "size": 500_000_000},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            resp = client.get("/api/benchmark/models?url=http://test:11434")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"
            assert len(data["models"]) == 2
            # Should be sorted by size ascending
            assert data["models"][0]["name"] == "model-b"

    def test_models_connection_error(self, client):
        import requests as req_lib
        with patch("frontend.blueprints.benchmark_bp.requests.get",
                    side_effect=req_lib.ConnectionError("refused")):
            resp = client.get("/api/benchmark/models?url=http://bad:1234")
            assert resp.status_code == 503

    def test_start_requires_models(self, client):
        resp = client.post("/api/benchmark/start",
                           data=json.dumps({"models": []}),
                           content_type="application/json")
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

        resp = client.get("/api/benchmark/results/auto_benchmark_results_20260101_120000.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["data"][0]["model"] == "test"

    def test_results_invalid_filename(self, client):
        resp = client.get("/api/benchmark/results/malicious_file.json")
        assert resp.status_code == 400
