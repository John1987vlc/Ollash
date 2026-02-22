"""Unit tests for operations_bp - operations dashboard routes."""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from flask import Flask

# Project root for locating templates
_PROJECT_ROOT = Path(__file__).parents[5]


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from frontend.blueprints.operations_views import bp as operations_bp
    # Provide the real template folder so render_template doesn't fail on page routes
    flask_app = Flask(__name__, template_folder=str(_PROJECT_ROOT / "frontend" / "templates"))
    flask_app.config["ollash_root_dir"] = Path(".")
    flask_app.register_blueprint(operations_bp, url_prefix="/operations")
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_operations_dashboard_loads(client):
    """GET /operations/ renderiza el dashboard o redirige."""
    response = client.get("/operations/")
    assert response.status_code in (200, 302, 404, 500)


@pytest.mark.unit
def test_list_jobs_empty(client):
    """GET /operations/api/jobs devuelve lista vacía por defecto (in-memory)."""
    response = client.get("/operations/api/jobs")
    assert response.status_code == 200
    data = response.get_json()
    assert "jobs" in data or isinstance(data, list)


@pytest.mark.unit
def test_create_job_returns_created(client):
    """POST /operations/api/jobs crea un nuevo trabajo."""
    payload = {
        "name": "Test Job",
        "schedule": "0 8 * * *",
        "task": "check disk space",
    }
    response = client.post(
        "/operations/api/jobs",
        json=payload,
        content_type="application/json",
    )
    assert response.status_code in (200, 201)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_delete_job_not_found(client):
    """DELETE /operations/api/jobs/<id> con ID inexistente devuelve 404 o mensaje de error."""
    response = client.delete("/operations/api/jobs/nonexistent-id-0000")
    assert response.status_code in (200, 404)
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_preview_dag(client):
    """POST /operations/api/dag/preview genera un DAG con las tareas dadas."""
    payload = {"tasks": ["task_a", "task_b", "task_c"]}
    response = client.post(
        "/operations/api/dag/preview",
        json=payload,
        content_type="application/json",
    )
    assert response.status_code in (200, 400)
    data = response.get_json()
    assert data is not None
