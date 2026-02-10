"""Unit tests for the Ollash Web UI (src/web/)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with mocked dependencies."""
    # Create minimal config
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps({
        "model": "test-model",
        "ollama_url": "http://localhost:11434",
        "timeout": 30,
        "max_tokens": 1024,
        "temperature": 0.5,
        "history_limit": 10,
        "sandbox": "limited",
        "project_root": ".",
        "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
        "models": {"default": "test-model", "coding": "test-model",
                   "reasoning": "test-model", "orchestration": "test-model",
                   "summarization": "test-model", "self_correction": "test-model",
                   "embedding": "test-model"},
        "auto_agent_llms": {
            "prototyper_model": "test", "coder_model": "test",
            "planner_model": "test", "generalist_model": "test",
            "suggester_model": "test", "improvement_planner_model": "test",
            "senior_reviewer_model": "test"
        },
        "auto_agent_timeouts": {
            "prototyper": 60, "coder": 60, "planner": 60,
            "generalist": 60, "suggester": 60,
            "improvement_planner": 60, "senior_reviewer": 60
        }
    }))

    # Create prompts directory
    prompts_dir = tmp_path / "prompts" / "orchestrator"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "default_orchestrator.json").write_text(json.dumps({
        "system_prompt": "You are a test agent.",
        "tools": ["plan_actions", "select_agent_type"]
    }))

    # Create other prompt dirs needed by DefaultAgent
    for domain in ["code", "network", "system", "cybersecurity"]:
        d = tmp_path / "prompts" / domain
        d.mkdir(parents=True, exist_ok=True)
        (d / f"default_{domain}_agent.json" if domain != "code" else d / "default_agent.json").write_text(
            json.dumps({"system_prompt": f"You are a {domain} agent.", "tools": []})
        )

    # Create logs dir
    (tmp_path / "logs").mkdir()

    # Patch AutoAgent and DefaultAgent to prevent real Ollama connections
    with patch("src.web.blueprints.auto_agent_bp.AutoAgent"), \
         patch("src.web.blueprints.benchmark_bp.ModelBenchmarker"):
        from src.web.app import create_app
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
        with patch("src.web.blueprints.chat_bp._session_manager") as mock_mgr:
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
        with patch("src.web.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            mock_mgr.create_session.return_value = "abc123"

            resp = client.post("/api/chat",
                               data=json.dumps({"message": "scan ports", "agent_type": "cybersecurity"}),
                               content_type="application/json")
            assert resp.status_code == 200
            mock_mgr.create_session.assert_called_once_with(None, "cybersecurity")

    def test_chat_stream_404_unknown_session(self, client):
        with patch("src.web.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            resp = client.get("/api/chat/stream/nonexistent")
            assert resp.status_code == 404

    def test_chat_max_sessions_error(self, client):
        with patch("src.web.blueprints.chat_bp._session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            mock_mgr.create_session.side_effect = RuntimeError("Maximum concurrent sessions (5) reached.")

            resp = client.post("/api/chat",
                               data=json.dumps({"message": "hello"}),
                               content_type="application/json")
            assert resp.status_code == 429


# ==================== Benchmark Blueprint ====================

class TestBenchmarkBlueprint:
    def test_models_endpoint(self, client):
        with patch("src.web.blueprints.benchmark_bp.requests.get") as mock_get, \
             patch("src.web.blueprints.benchmark_bp.ModelBenchmarker") as MockBench:
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
        with patch("src.web.blueprints.benchmark_bp.requests.get",
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


# ==================== Chat Event Bridge ====================

class TestChatEventBridge:
    def test_push_and_iter(self):
        from src.web.services.chat_event_bridge import ChatEventBridge
        bridge = ChatEventBridge()
        bridge.push_event("test", {"key": "value"})
        bridge.close()

        events = list(bridge.iter_events())
        # Should have at least the test event and stream_end
        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) >= 2  # test event + stream_end

    def test_close_sends_stream_end(self):
        from src.web.services.chat_event_bridge import ChatEventBridge
        bridge = ChatEventBridge()
        bridge.close()

        events = list(bridge.iter_events())
        joined = "".join(events)
        assert "stream_end" in joined


# ==================== Chat Session Manager ====================

class TestChatSessionManager:
    def test_create_session(self, tmp_path):
        # Need config for DefaultAgent
        config_dir = tmp_path / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "settings.json").write_text(json.dumps({
            "model": "test", "ollama_url": "http://localhost:11434",
            "timeout": 30, "max_tokens": 1024, "temperature": 0.5,
            "history_limit": 10, "sandbox": "limited", "project_root": ".",
            "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
            "models": {"default": "test", "coding": "test", "reasoning": "test",
                       "orchestration": "test", "summarization": "test",
                       "self_correction": "test", "embedding": "test"}
        }))
        prompts_dir = tmp_path / "prompts" / "orchestrator"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "default_orchestrator.json").write_text(
            json.dumps({"system_prompt": "test", "tools": []})
        )
        for domain in ["code", "network", "system", "cybersecurity"]:
            d = tmp_path / "prompts" / domain
            d.mkdir(parents=True, exist_ok=True)
            fname = "default_agent.json" if domain == "code" else f"default_{domain}_agent.json"
            (d / fname).write_text(json.dumps({"system_prompt": "test", "tools": []}))

        with patch("src.web.services.chat_session_manager.DefaultAgent"):
            from src.web.services.chat_session_manager import ChatSessionManager
            mgr = ChatSessionManager(tmp_path)
            session_id = mgr.create_session()
            assert session_id is not None
            assert mgr.get_session(session_id) is not None

    def test_max_sessions_limit(self):
        with patch("src.web.services.chat_session_manager.DefaultAgent"):
            from src.web.services.chat_session_manager import ChatSessionManager
            mgr = ChatSessionManager(Path("."))
            for _ in range(5):
                mgr.create_session()
            with pytest.raises(RuntimeError, match="Maximum"):
                mgr.create_session()

    def test_agent_type_sets_active_type(self):
        with patch("src.web.services.chat_session_manager.DefaultAgent") as MockAgent:
            mock_instance = MockAgent.return_value
            mock_instance._agent_tool_name_mappings = {
                "code": ["read_file", "write_file"],
                "orchestrator": ["plan_actions"],
            }
            mock_instance.active_agent_type = "orchestrator"
            mock_instance.active_tool_names = ["plan_actions"]

            from src.web.services.chat_session_manager import ChatSessionManager
            mgr = ChatSessionManager(Path("."))
            mgr.create_session(agent_type="code")

            # Should have set agent type on the mock
            assert mock_instance.active_agent_type == "code"
            assert mock_instance.active_tool_names == ["read_file", "write_file"]
