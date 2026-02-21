import pytest
from unittest.mock import MagicMock
from pathlib import Path
from flask import Flask
import sys

# Mock psutil globally for these tests
mock_psutil = MagicMock()
sys.modules["psutil"] = mock_psutil


@pytest.fixture
def app():
    from frontend.blueprints.system_health_bp import system_health_bp, init_app

    app = Flask(__name__)
    app.config["ollash_root_dir"] = Path(".")
    app.register_blueprint(system_health_bp)
    init_app(app)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_system_health_endpoint_structure(client):
    """Verifica que el endpoint devuelva todas las claves requeridas."""
    mock_psutil.cpu_percent.return_value = 10.0
    mock_mem = MagicMock()
    mock_mem.total = 16 * 1024**3
    mock_mem.used = 8 * 1024**3
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "ok"
    assert "cpu_percent" in data
    assert "ram_percent" in data


def test_system_health_logic_mocked(client):
    """Verifica la lógica interna simulando psutil."""
    mock_psutil.cpu_percent.return_value = 25.5

    mock_mem = MagicMock()
    mock_mem.total = 16 * 1024**3
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    response = client.get("/api/system/health")
    data = response.get_json()

    assert data["cpu_percent"] > 0
    assert "ram_percent" in data
    assert data["ram_total_gb"] == pytest.approx(16.0, rel=0.1)
