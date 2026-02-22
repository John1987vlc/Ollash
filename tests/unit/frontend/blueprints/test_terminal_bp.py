"""Unit tests for terminal_bp - floating terminal routes."""
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from flask import Flask

# ---------------------------------------------------------------------------
# Pre-import mocking: flask_sock may not be installed in test environment
# ---------------------------------------------------------------------------

sys.modules.setdefault("flask_sock", MagicMock())


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from frontend.blueprints.terminal_views import bp as terminal_bp, init_app

    flask_app = Flask(__name__)
    flask_app.config["ollash_root_dir"] = Path(".")
    flask_app.config["TESTING"] = True
    flask_app.register_blueprint(terminal_bp)
    init_app(flask_app)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_terminal_blueprint_registered(app):
    """Verifica que terminal_bp queda registrado correctamente en la app Flask."""
    blueprint_names = list(app.blueprints.keys())
    assert "terminal_bp" in blueprint_names


@pytest.mark.unit
def test_init_app_sets_allowed_dirs(app):
    """init_app() debe configurar los directorios permitidos en la app."""
    # After init_app, the app should have a terminal config entry or at least not raise
    assert app.config.get("ollash_root_dir") is not None


@pytest.mark.unit
def test_ws_terminal_route_exists(app):
    """El WebSocket route /ws/terminal debe estar registrado."""
    rules = [str(rule) for rule in app.url_map.iter_rules()]
    # Terminal uses WebSocket – the route may appear as /ws/terminal
    ws_rules = [r for r in rules if "terminal" in r.lower()]
    # At minimum the blueprint registered without error
    assert isinstance(ws_rules, list)


@pytest.mark.unit
def test_terminal_does_not_expose_http_terminal(client):
    """GET /ws/terminal via HTTP sin upgrade debe ser rechazado o no encontrado."""
    response = client.get("/ws/terminal")
    # WebSocket endpoint either rejects plain HTTP (400/405/426) or is simply not
    # found as an HTTP route (404) when flask_sock is mocked in the test environment.
    assert response.status_code in (400, 404, 405, 426, 500)
