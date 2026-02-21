import pytest
from unittest.mock import MagicMock
from flask import Flask
from pathlib import Path

# Import blueprint
from frontend.blueprints.artifacts_bp import artifacts_bp, init_app


@pytest.fixture
def app():
    """Create a Flask app for testing artifacts endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": Path("/tmp/ollash"), "config": {}})
    init_app(app)
    app.register_blueprint(artifacts_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def mock_manager(app):
    """
    Inject mocked manager into the app context to isolate blueprint routes.
    """
    mock = MagicMock()
    with app.app_context():
        app._artifact_manager = mock
    return mock


class TestArtifactsBlueprint:
    """Test suite for Interactive Artifacts endpoints."""

    # --- CRUD Tests ---

    def test_list_artifacts_success(self, client, mock_manager):
        mock_art = MagicMock()
        mock_art.to_dict.return_value = {"id": "a1", "type": "report"}
        mock_manager.list_artifacts.return_value = [mock_art]

        response = client.get("/api/artifacts/?type=report")

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 1
        assert data["type_filter"] == "report"
        mock_manager.list_artifacts.assert_called_with("report")

    def test_get_artifact_success(self, client, mock_manager):
        mock_art = MagicMock()
        mock_art.to_dict.return_value = {"id": "a1", "title": "Test"}
        mock_manager.get_artifact.return_value = mock_art

        response = client.get("/api/artifacts/a1")

        assert response.status_code == 200
        assert response.get_json()["id"] == "a1"

    def test_get_artifact_not_found(self, client, mock_manager):
        mock_manager.get_artifact.return_value = None

        response = client.get("/api/artifacts/unknown")
        assert response.status_code == 404

    def test_delete_artifact_success(self, client, mock_manager):
        mock_manager.delete_artifact.return_value = True

        response = client.delete("/api/artifacts/a1")
        assert response.status_code == 200
        assert response.get_json()["status"] == "deleted"

    # --- Creation Tests ---

    def test_create_report_success(self, client, mock_manager):
        mock_manager.create_report.return_value = "rep_123"

        payload = {"title": "Annual Report", "sections": [{"heading": "Intro", "content": "Hello"}]}

        response = client.post("/api/artifacts/report", json=payload)

        assert response.status_code == 201
        assert response.get_json()["artifact_id"] == "rep_123"
        mock_manager.create_report.assert_called_once()

    def test_create_report_missing_fields(self, client):
        response = client.post("/api/artifacts/report", json={"title": "No sections"})
        assert response.status_code == 400

    def test_create_diagram_success(self, client, mock_manager):
        mock_manager.create_diagram.return_value = "diag_456"

        payload = {"title": "Flow", "mermaid_code": "graph LR; A-->B"}

        response = client.post("/api/artifacts/diagram", json=payload)
        assert response.status_code == 201
        assert response.get_json()["artifact_id"] == "diag_456"

    def test_create_checklist_success(self, client, mock_manager):
        mock_manager.create_checklist.return_value = "chk_789"

        payload = {"title": "To-Do", "items": [{"id": "1", "label": "task", "completed": False}]}

        response = client.post("/api/artifacts/checklist", json=payload)
        assert response.status_code == 201

    # --- Rendering Tests ---

    def test_render_artifact_success(self, client, mock_manager):
        mock_art = MagicMock()
        mock_art.type = "report"
        mock_art.title = "Test Rep"
        mock_manager.get_artifact.return_value = mock_art
        mock_manager.render_artifact_html.return_value = "<p>Report Content</p>"

        response = client.get("/api/artifacts/a1/render")

        assert response.status_code == 200
        data = response.get_json()
        assert data["html"] == "<p>Report Content</p>"
        assert data["type"] == "report"

    def test_render_batch_success(self, client, mock_manager):
        mock_art = MagicMock()
        mock_art.type = "code"
        mock_art.title = "Code Art"
        mock_manager.get_artifact.return_value = mock_art
        mock_manager.render_artifact_html.return_value = "<code>...</code>"

        response = client.post("/api/artifacts/render-batch", json={"artifact_ids": ["art1", "art2"]})

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 2
        assert "art1" in data["rendered"]
        assert "art2" in data["rendered"]

    # --- Error Handling ---

    def test_generic_exception_handling(self, client, mock_manager):
        mock_manager.list_artifacts.side_effect = Exception("System IO Error")

        response = client.get("/api/artifacts/")

        assert response.status_code == 500
        assert "System IO Error" in response.get_json()["error"]
