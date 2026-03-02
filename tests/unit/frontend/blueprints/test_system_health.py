"""
System health router unit tests — migrated from Flask blueprint tests.
"""

import sys
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from backend.api.app import create_app

# Mock psutil before importing the router
mock_psutil = MagicMock()
sys.modules["psutil"] = mock_psutil


@pytest.fixture
def app(tmp_path):
    _app = create_app()
    _app.state.event_publisher = MagicMock()
    _app.state.alert_manager = MagicMock()
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
def test_system_health_endpoint_structure(client):
    """Verifica que el endpoint devuelva todas las claves requeridas."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "cpu" in data
    assert "ram" in data


@pytest.mark.unit
def test_system_health_models_present(client):
    """Verifica que el campo models esté presente en la respuesta."""
    response = client.get("/api/health/")
    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)
