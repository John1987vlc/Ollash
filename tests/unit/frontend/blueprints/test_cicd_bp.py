import pytest
from unittest.mock import MagicMock, AsyncMock
import sys
from flask import Flask

# Import the blueprint
from frontend.blueprints.cicd_bp import cicd_bp


@pytest.fixture
def mock_healer():
    """Create a mock for the CICDHealer."""
    healer = MagicMock()
    # Mock the async methods
    healer.analyze_failure = AsyncMock()
    healer.generate_fix = AsyncMock()
    return healer


@pytest.fixture
def app(mock_healer, monkeypatch):
    """Create a Flask app for testing CICD endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True})

    # Target the module directly to patch the global _healer
    target_module = sys.modules["frontend.blueprints.cicd_bp"]
    monkeypatch.setattr(target_module, "_healer", mock_healer)

    app.register_blueprint(cicd_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestCICDBlueprint:
    """Test suite for CI/CD Auto-Healing endpoints."""

    def test_analyze_failure_success(self, client, mock_healer):
        # Setup mock analysis result
        mock_analysis = MagicMock()
        mock_analysis.to_dict.return_value = {"error_type": "compilation", "details": "syntax error"}
        mock_healer.analyze_failure.return_value = mock_analysis

        response = client.post("/api/cicd/analyze", json={"log": "ERROR: syntax error at line 10"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["analysis"]["error_type"] == "compilation"
        mock_healer.analyze_failure.assert_called_once()

    def test_analyze_failure_missing_log(self, client):
        response = client.post("/api/cicd/analyze", json={})
        assert response.status_code == 400
        assert "log field required" in response.get_json()["error"]

    def test_generate_fix_success(self, client, mock_healer):
        # Setup mock analysis and fix
        mock_analysis = MagicMock()
        mock_healer.analyze_failure.return_value = mock_analysis
        mock_healer.generate_fix.return_value = "fixed_code.py"

        response = client.post("/api/cicd/fix", json={"log": "test log", "project_files": {"app.py": "code"}})

        assert response.status_code == 200
        assert response.get_json()["fix"] == "fixed_code.py"
        mock_healer.generate_fix.assert_called_once()

    def test_healer_not_available(self, client, monkeypatch):
        # Force _healer to None
        target_module = sys.modules["frontend.blueprints.cicd_bp"]
        monkeypatch.setattr(target_module, "_healer", None)

        response = client.post("/api/cicd/analyze", json={"log": "test"})
        assert response.status_code == 503
        assert "not available" in response.get_json()["error"]

    def test_analyze_failure_exception(self, client, mock_healer):
        mock_healer.analyze_failure.side_effect = Exception("LLM Timeout")

        response = client.post("/api/cicd/analyze", json={"log": "test"})
        assert response.status_code == 500
        assert "LLM Timeout" in response.get_json()["error"]
