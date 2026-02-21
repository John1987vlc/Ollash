import pytest
from unittest.mock import MagicMock, AsyncMock
import sys
from flask import Flask

# Import the blueprint and its source module
from frontend.blueprints.webhooks_bp import webhooks_bp, init_app


@pytest.fixture
def app():
    """Create a Flask app for testing webhooks."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "SECRET_KEY": "test_secret"})
    init_app(app)
    app.register_blueprint(webhooks_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_webhook_system(monkeypatch):
    """
    Forcefully mock the manager using module-level patching.
    """
    mock_wm = MagicMock()
    mock_wm.send_to_webhook = AsyncMock()

    target_module = sys.modules["frontend.blueprints.webhooks_bp"]

    # Mock the get_webhook_manager function
    monkeypatch.setattr(target_module, "get_webhook_manager", lambda: mock_wm)

    return mock_wm


class TestWebhooksBlueprint:
    """Test suite for Webhook management endpoints (Synchronous logic)."""

    def test_list_webhooks_success(self, client, mock_webhook_system):
        mock_status = [{"name": "slack", "type": "slack", "enabled": True}]
        mock_webhook_system.get_webhook_status.return_value = mock_status

        response = client.get("/api/webhooks/")

        assert response.status_code == 200
        data = response.get_json()
        assert data["webhooks"] == mock_status

    def test_register_webhook_success(self, client, mock_webhook_system):
        mock_webhook_system.register_webhook.return_value = True

        response = client.post(
            "/api/webhooks/register", json={"name": "my-webhook", "url": "http://example.com/hook", "type": "slack"}
        )

        assert response.status_code == 200
        assert "registered" in response.get_json()["message"]
        mock_webhook_system.register_webhook.assert_called_once()

    def test_register_webhook_missing_params(self, client):
        response = client.post("/api/webhooks/register", json={"name": "test"})
        assert response.status_code == 400
        assert "Missing name or url" in response.get_json()["message"]

    def test_generic_exception_handling(self, client, mock_webhook_system):
        mock_webhook_system.get_webhook_status.side_effect = Exception("System Crash")
        response = client.get("/api/webhooks/")
        assert response.status_code == 500
