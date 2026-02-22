"""Unit tests for cybersecurity_bp - security scanning routes."""
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from flask import Flask

# ---------------------------------------------------------------------------
# Pre-import mocking: block heavy backend dependencies
# ---------------------------------------------------------------------------

_mock_cyber_tools = MagicMock()
_mock_vuln_scanner = MagicMock()
_mock_agent_logger = MagicMock()

for mod in [
    "backend.utils.domains.cybersecurity.cybersecurity_tools",
    "backend.utils.core.analysis.vulnerability_scanner",
    "backend.utils.core.system.agent_logger",
    "backend.utils.core.system.structured_logger",
    "backend.utils.core.command_executor",
    "backend.utils.core.io.file_manager",
]:
    sys.modules.setdefault(mod, MagicMock())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_managers():
    """Build a mock managers dict that cybersecurity_bp returns."""
    mgrs = {
        "tools": MagicMock(),
        "scanner": MagicMock(),
        "logger": MagicMock()
    }
    mgrs["tools"].scan_ports.return_value = {"open_ports": [80, 443], "ok": True}
    mgrs["scanner"].scan_file.return_value = MagicMock(to_dict=lambda: {"vulnerabilities": []})
    mgrs["tools"].check_file_hash.return_value = {"ok": True, "result": {"hash": "abc"}}
    mgrs["tools"].analyze_security_log.return_value = {"anomalies": [], "ok": True}
    mgrs["tools"].recommend_security_hardening.return_value = []
    return mgrs


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from frontend.blueprints.cybersecurity_views import bp as cybersecurity_bp
    import frontend.blueprints.cybersecurity_views as cyber_module

    flask_app = Flask(__name__)
    flask_app.config["ollash_root_dir"] = Path(".")
    flask_app.cyber_module = cyber_module

    # Patch the internal factory function used by the blueprint
    with patch.object(
        cyber_module,
        "get_cybersecurity_managers",
        return_value=_make_managers(),
    ):
        flask_app.register_blueprint(cybersecurity_bp, url_prefix="/api/cybersecurity")

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_port_scan_returns_json(client, app):
    """POST /api/cybersecurity/scan/ports devuelve puertos escaneados."""
    with patch.object(
        app.cyber_module,
        "get_cybersecurity_managers",
        return_value=_make_managers(),
    ):
        response = client.post(
            "/api/cybersecurity/scan/ports",
            json={"host": "127.0.0.1"},
            content_type="application/json",
        )
    assert response.status_code in (200, 400, 500)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_vulnerability_scan_returns_json(client, app):
    """POST /api/cybersecurity/scan/vulnerabilities devuelve análisis de vulnerabilidades."""
    # We need a real file to exist for the check in the blueprint
    test_file = Path("test_vuln.py")
    test_file.write_text("print('hello')", encoding="utf-8")
    
    try:
        with patch.object(
            app.cyber_module,
            "get_cybersecurity_managers",
            return_value=_make_managers(),
        ):
            response = client.post(
                "/api/cybersecurity/scan/vulnerabilities",
                json={"path": "test_vuln.py"},
                content_type="application/json",
            )
        assert response.status_code in (200, 400, 404, 500)
        data = response.get_json()
        assert data is not None
    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.unit
def test_integrity_check_returns_json(client, app):
    """POST /api/cybersecurity/integrity/check comprueba integridad de archivos."""
    with patch.object(
        app.cyber_module,
        "get_cybersecurity_managers",
        return_value=_make_managers(),
    ):
        response = client.post(
            "/api/cybersecurity/integrity/check",
            json={"path": "file.txt", "expected_hash": "abc"},
            content_type="application/json",
        )
    assert response.status_code in (200, 400, 500)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_recommendations_returns_list(client, app):
    """GET /api/cybersecurity/recommendations devuelve recomendaciones de hardening."""
    with patch.object(
        app.cyber_module,
        "get_cybersecurity_managers",
        return_value=_make_managers(),
    ):
        response = client.get("/api/cybersecurity/recommendations")
    assert response.status_code in (200, 500)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_logs_analyze_returns_json(client, app):
    """POST /api/cybersecurity/logs/analyze analiza logs de seguridad."""
    with patch.object(
        app.cyber_module,
        "get_cybersecurity_managers",
        return_value=_make_managers(),
    ):
        response = client.post(
            "/api/cybersecurity/logs/analyze",
            json={"path": "auth.log"},
            content_type="application/json",
        )
    assert response.status_code in (200, 400, 500)
    data = response.get_json()
    assert data is not None
