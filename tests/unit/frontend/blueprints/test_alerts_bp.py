import pytest
from unittest.mock import MagicMock, patch
import sys
from flask import Flask

# Import the blueprint
from frontend.blueprints.alerts_bp import alerts_bp


@pytest.fixture
def mock_alert_manager():
    return MagicMock()


@pytest.fixture
def mock_event_publisher():
    return MagicMock()


@pytest.fixture
def app(mock_alert_manager, mock_event_publisher):
    app = Flask(__name__)
    app.config.update({"TESTING": True, "alert_manager": mock_alert_manager, "event_publisher": mock_event_publisher})
    app.register_blueprint(alerts_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestAlertsBlueprint:
    """Test suite for Alerts API and SSE stream endpoints with full lifecycle verification."""

    def test_get_alerts_success(self, client, mock_alert_manager):
        mock_alerts = [{"id": "cpu_high", "status": "active"}]
        mock_alert_manager.get_active_alerts.return_value = mock_alerts
        response = client.get("/api/alerts")
        assert response.status_code == 200
        assert response.get_json()["alerts"] == mock_alerts

    def test_get_alert_history_limit(self, client, mock_alert_manager):
        mock_alert_manager.get_alert_history.return_value = []
        response = client.get("/api/alerts/history?limit=10")
        assert response.status_code == 200
        mock_alert_manager.get_alert_history.assert_called_with(limit=10)

    def test_disable_alert_success(self, client, mock_alert_manager):
        mock_alert_manager.disable_alert.return_value = True
        response = client.post("/api/alerts/a1/disable")
        assert response.status_code == 200
        mock_alert_manager.disable_alert.assert_called_with("a1")

    def test_stream_alerts_no_publisher(self, app, client):
        app.config["event_publisher"] = None
        response = client.get("/api/alerts/stream")
        iterator = response.response
        first_chunk = next(iterator)
        assert b"not initialized" in first_chunk
        iterator.close()

    def test_stream_alerts_event_delivery(self, client, mock_event_publisher):
        """
        Validates event delivery and proper cleanup (unsubscription).
        """
        target_module = sys.modules["frontend.blueprints.alerts_bp"]

        mock_q = MagicMock()
        # Return our event then raise GeneratorExit to simulate stream closing
        mock_q.get.side_effect = [("ui_alert", {"msg": "test"}), GeneratorExit]

        with patch.object(target_module, "queue") as mock_queue_mod:
            mock_queue_mod.Queue.return_value = mock_q

            response = client.get("/api/alerts/stream")
            iterator = response.response

            # Blueprint code yield event then data
            chunk1 = next(iterator)
            chunk2 = next(iterator)

            assert b"event: ui_alert" in chunk1
            assert b'{"msg": "test"}' in chunk2

            # Explicitly close the iterator to trigger finally block in the view
            iterator.close()

            # Verify unsubscription happened
            assert mock_event_publisher.unsubscribe.called

    def test_generic_exception_handling(self, client, mock_alert_manager):
        mock_alert_manager.get_active_alerts.side_effect = Exception("System Crash")
        response = client.get("/api/alerts")
        assert response.status_code == 500
