import pytest
from unittest.mock import MagicMock
import sys
from flask import Flask

# Import the blueprint
from frontend.blueprints.cost_bp import cost_bp


@pytest.fixture
def mock_analyzer():
    """Create a mock for the CostAnalyzer."""
    analyzer = MagicMock()
    return analyzer


@pytest.fixture
def app(mock_analyzer, monkeypatch):
    """Create a Flask app for testing cost endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True})

    # Access the module directly to patch global variables
    target_module = sys.modules["frontend.blueprints.cost_bp"]
    monkeypatch.setattr(target_module, "_cost_analyzer", mock_analyzer)

    # Use a mock queue to control the flow and avoid infinite loops
    mock_queue = MagicMock()
    monkeypatch.setattr(target_module, "_cost_event_queue", mock_queue)

    app.register_blueprint(cost_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def bp_module():
    """Access the cost blueprint module."""
    return sys.modules["frontend.blueprints.cost_bp"]


class TestCostBlueprint:
    """Test suite for Model Cost Analyzer endpoints with graceful loop exit."""

    def test_get_cost_report_success(self, client, mock_analyzer):
        mock_report = MagicMock()
        mock_report.to_dict.return_value = {"total_cost": 1.25, "currency": "USD"}
        mock_analyzer.get_report.return_value = mock_report

        response = client.get("/api/costs/report")

        assert response.status_code == 200
        data = response.get_json()["report"]
        assert data["total_cost"] == 1.25

    def test_get_cost_report_unavailable(self, client, bp_module, monkeypatch):
        monkeypatch.setattr(bp_module, "_cost_analyzer", None)
        response = client.get("/api/costs/report")
        assert response.status_code == 503

    def test_get_suggestions_success(self, client, mock_analyzer):
        mock_sug = MagicMock()
        mock_sug.to_dict.return_value = {"from": "m1", "to": "m2"}
        mock_analyzer.suggest_downgrades.return_value = [mock_sug]

        response = client.get("/api/costs/suggestions")
        assert response.status_code == 200
        assert len(response.get_json()["suggestions"]) == 1

    def test_get_costs_by_model(self, client, mock_analyzer):
        mock_analyzer.get_report.return_value = {"by_model": {"m1": 100}}
        response = client.get("/api/costs/by-model")
        assert response.status_code == 200
        assert response.get_json()["by_model"]["m1"] == 100

    def test_get_cost_history_limit(self, client, mock_analyzer):
        mock_analyzer.get_report.return_value = {"history": [{"ts": 1}]}
        response = client.get("/api/costs/history?limit=1")
        assert len(response.get_json()["history"]) == 1

    def test_cost_stream_success(self, client, bp_module):
        """
        Test SSE stream using a finite generator mock.
        Instead of calling the real generate() which has 'while True',
        we test the response object configuration and mimetype.
        """
        mock_queue = bp_module._cost_event_queue
        # Return one item then stop
        mock_queue.get.side_effect = [{"msg": "test"}]

        # We use response.iter_encoded() to manually consume one item
        # without falling into the infinite loop of the response data property
        response = client.get("/api/costs/stream")

        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"

        # We check the first part of the stream manually
        # This is the safest way to test infinite generators in Flask
        iterator = response.response
        first_chunk = next(iterator)
        assert b"cost_update" in first_chunk
        assert b"test" in first_chunk

    def test_endpoint_error_handling(self, client, mock_analyzer):
        mock_analyzer.get_report.side_effect = Exception("Crash")
        response = client.get("/api/costs/report")
        assert response.status_code == 500
