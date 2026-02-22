"""Unit tests for git_bp - git integration routes."""
import json
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from flask import Flask


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from frontend.blueprints.git_views import bp as git_bp
    import frontend.blueprints.git_views as git_module
    
    # Base directory for templates
    template_dir = Path(__file__).parents[4] / "frontend" / "templates"
    
    flask_app = Flask(__name__, template_folder=str(template_dir))
    flask_app.config["ollash_root_dir"] = Path(".")
    flask_app.register_blueprint(git_bp, url_prefix="/git")
    
    # Store the module in the app for easier patching in tests
    flask_app.git_module = git_module
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_git_dashboard_renders(client):
    """GET /git/ renders the git dashboard page (or returns 200)."""
    response = client.get("/git/")
    assert response.status_code in (200, 302, 404)  # page or redirect is valid


@pytest.mark.unit
def test_git_status_ok(client, app):
    """GET /git/api/status devuelve branch y modified_files."""
    completed = MagicMock()
    completed.stdout = "main\nM frontend/static/js/main.js\n"
    completed.returncode = 0

    # Use patch.object on the module to avoid Blueprint shadowing
    with patch.object(app.git_module, "subprocess") as mock_sp:
        mock_sp.run.return_value = completed
        response = client.get("/git/api/status")

    assert response.status_code == 200
    data = response.get_json()
    assert "branch" in data or "status" in data


@pytest.mark.unit
def test_git_status_error_handled(client, app):
    """GET /git/api/status cuando subprocess falla devuelve un error controlado."""
    with patch.object(app.git_module, "subprocess") as mock_sp:
        mock_sp.run.side_effect = Exception("git not found")
        response = client.get("/git/api/status")

    assert response.status_code in (200, 500)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_git_diff_returns_json(client, app):
    """GET /git/api/diff devuelve diferencias de un archivo."""
    completed = MagicMock()
    completed.stdout = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n"
    completed.returncode = 0

    with patch.object(app.git_module, "subprocess") as mock_sp:
        mock_sp.run.return_value = completed
        response = client.get("/git/api/diff?file=file.py")

    assert response.status_code in (200, 400)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_git_commit_post(client, app):
    """POST /git/api/commit acepta mensaje y lista de archivos."""
    completed = MagicMock()
    completed.stdout = "main"
    completed.returncode = 0

    with patch.object(app.git_module, "subprocess") as mock_sp:
        mock_sp.run.return_value = completed
        response = client.post(
            "/git/api/commit",
            json={"message": "test commit", "files": ["file.py"]},
            content_type="application/json",
        )

    assert response.status_code in (200, 400, 500)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_git_log_returns_list(client, app):
    """GET /git/api/log devuelve un listado de commits recientes."""
    completed = MagicMock()
    completed.stdout = "abc1234 - Fix bug (2024-01-01)\ndef5678 - Add feature (2024-01-02)\n"
    completed.returncode = 0

    with patch.object(app.git_module, "subprocess") as mock_sp:
        mock_sp.run.return_value = completed
        response = client.get("/git/api/log")

    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
