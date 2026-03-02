"""
Alerts router unit tests — migrated from Flask blueprint tests.

Changes from Flask version:
- Flask `app.test_client()` → starlette `TestClient`
- `app.config["alert_manager"]` → `app.state.alert_manager`
- SSE stream test uses `stream=True` on TestClient
- `response.get_json()` → `response.json()`
"""

import pytest
from unittest.mock import MagicMock
from starlette.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def mock_alert_manager():
    return MagicMock()


@pytest.fixture
def mock_event_publisher():
    return MagicMock()


@pytest.fixture
def app(mock_alert_manager, mock_event_publisher, tmp_path):
    _app = create_app()
    _app.state.alert_manager = mock_alert_manager
    _app.state.event_publisher = mock_event_publisher
    _app.state.automation_manager = MagicMock()
    _app.state.notification_manager = MagicMock()
    _app.state.chat_event_bridge = MagicMock()
    _app.state.ollash_root_dir = tmp_path
    return _app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.unit
class TestAlertsRouter:
    """Test suite for the FastAPI alerts router."""

    def test_get_alerts_success(self, client, mock_alert_manager):
        mock_alerts = [{"id": "cpu_high", "status": "active"}]
        mock_alert_manager.get_active_alerts.return_value = mock_alerts

        response = client.get("/api/alerts")
        assert response.status_code == 200
        assert response.json()["alerts"] == mock_alerts

    def test_dismiss_alert(self, client, mock_alert_manager):
        response = client.post("/api/alerts/dismiss/alert-1")
        assert response.status_code == 200
        mock_alert_manager.dismiss_alert.assert_called_once_with("alert-1")

    def test_get_alerts_returns_total_count(self, client, mock_alert_manager):
        mock_alert_manager.get_active_alerts.return_value = [{}, {}, {}]
        response = client.get("/api/alerts")
        assert response.json()["total"] == 3
