import pytest
from unittest.mock import MagicMock, patch
import json
import sys
import queue
from flask import Flask

# Import the blueprint object
from frontend.blueprints.benchmark_bp import benchmark_bp, init_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a Flask app for testing benchmarks."""
    app = Flask(__name__)
    app.config.update(
        {
            "TESTING": True,
            "ollash_root_dir": tmp_path,
            "SECRET_KEY": "test_secret",
            "config": {"ollama_url": "http://localhost:11434"},
        }
    )

    # Access the module directly to bypass Blueprint object name shadowing
    target_module = sys.modules["frontend.blueprints.benchmark_bp"]

    # Inject global state directly into the module's globals
    monkeypatch.setattr(target_module, "_active_run", None)
    monkeypatch.setattr(target_module, "_ollash_root_dir", tmp_path)
    # Mock render_template to avoid file system lookups
    monkeypatch.setattr(target_module, "render_template", MagicMock(return_value="<html></html>"))

    init_app(app)
    app.register_blueprint(benchmark_bp)

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def bp_module():
    return sys.modules["frontend.blueprints.benchmark_bp"]


class TestBenchmarkBlueprint:
    """Test suite for Model Benchmarking and Optimization endpoints with total module-level isolation."""

    def test_benchmark_page_renders(self, client):
        response = client.get("/benchmark")
        assert response.status_code == 200

    def test_list_models_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "qwen3:latest", "size": 5000000000}, {"name": "nomic-embed-text", "size": 200000000}]
        }

        with patch("requests.get", return_value=mock_resp):
            response = client.get("/api/benchmark/models")
            assert response.status_code == 200
            data = response.get_json()
            assert len(data["models"]) == 2

    def test_start_benchmark_success(self, client, bp_module):
        payload = {"models": ["m1"]}
        with patch("threading.Thread") as mock_thread:
            response = client.post("/api/benchmark/start", json=payload)
            assert response.status_code == 200
            assert bp_module._active_run is not None
            assert mock_thread.called

    def test_start_benchmark_already_running(self, client, bp_module):
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        bp_module._active_run = {"thread": mock_thread}

        response = client.post("/api/benchmark/start", json={"models": ["test"]})
        assert response.status_code == 429

    def test_stream_benchmark_success(self, client, bp_module):
        event_queue = queue.Queue()
        event_queue.put(json.dumps({"type": "ping"}))
        event_queue.put(None)
        bp_module._active_run = {"queue": event_queue}

        response = client.get("/api/benchmark/stream")
        assert response.status_code == 200
        assert b'data: {"type": "ping"}' in response.data

    def test_radar_chart_data_success(self, client, bp_module, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        result_file = log_dir / "auto_benchmark_results_radar.json"

        mock_results = [
            {
                "model": "qwen3",
                "tokens_per_second": 45.0,
                "rubric_scores": {"strict_json_score": 1.0},
                "thematic_scores": {"Calidad_Codigo": 0.8},
            }
        ]
        result_file.write_text(json.dumps(mock_results))

        response = client.get("/api/benchmark/radar/qwen3")
        assert response.status_code == 200
        assert response.get_json()["dimensions"]["Format"] == 10.0

    def test_optimal_pipeline_success(self, client, bp_module, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        result_file = log_dir / "auto_benchmark_results_opt.json"

        mock_results = [{"model": "m1", "tokens_per_second": 50.0, "thematic_scores": {"Calidad_Codigo": 0.9}}]
        result_file.write_text(json.dumps(mock_results))

        response = client.get("/api/benchmark/optimal-pipeline")
        assert response.status_code == 200
        assert "pipeline" in response.get_json()

    def test_get_result_invalid_filename(self, client):
        response = client.get("/api/benchmark/results/bad.exe")
        assert response.status_code == 400
