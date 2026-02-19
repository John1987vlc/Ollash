import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from flask import Flask
from frontend.blueprints.system_health_bp import system_health_bp, init_app

@pytest.fixture
def app():
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
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.get_json()
    
    assert data["status"] == "ok"
    assert "cpu_percent" in data
    assert "ram_percent" in data
    assert "disk_percent" in data
    assert "net_sent_mb" in data
    assert "net_recv_mb" in data

def test_system_health_logic_mocked(client):
    """Verifica la lógica interna simulando psutil en el módulo del blueprint."""
    # Using the string path to patch psutil where it's used
    with patch("frontend.blueprints.system_health_bp.psutil") as mock_psutil:
        # psutil mock won't be None anymore
        mock_psutil.cpu_percent.return_value = 25.5
        
        mock_mem = MagicMock()
        mock_mem.total = 16*1024**3
        mock_mem.used = 8*1024**3
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem
        
        mock_disk = MagicMock()
        mock_disk.total = 500*1024**3
        mock_disk.used = 100*1024**3
        mock_disk.percent = 20.0
        mock_psutil.disk_usage.return_value = mock_disk
        
        mock_net = MagicMock()
        mock_net.bytes_sent = 100*1024**2
        mock_net.bytes_recv = 200*1024**2
        mock_psutil.net_io_counters.return_value = mock_net
        
        response = client.get("/api/system/health")
        data = response.get_json()
        
        assert data["cpu_percent"] == 25.5
        assert data["ram_percent"] == 50.0
        assert data["ram_total_gb"] == 16.0
        assert data["disk_percent"] == 20.0
        assert data["net_sent_mb"] == 100.0
        assert data["net_recv_mb"] == 200.0
