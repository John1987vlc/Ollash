import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from flask import Flask

# Import the blueprint
from frontend.blueprints.export_bp import export_bp


@pytest.fixture
def mock_export_manager():
    """Create a mock for the ExportManager."""
    manager = MagicMock()
    manager.deploy_to_github = AsyncMock()
    return manager


@pytest.fixture
def app(tmp_path, mock_export_manager, monkeypatch):
    """Create a Flask app for testing export endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": tmp_path})

    # Target module for patching globals
    target_module = sys.modules["frontend.blueprints.export_bp"]
    monkeypatch.setattr(target_module, "_export_manager", mock_export_manager)
    monkeypatch.setattr(target_module, "_ollash_root", tmp_path)

    app.register_blueprint(export_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestExportBlueprint:
    """Test suite for Project Export and Deployment endpoints."""

    def test_export_zip_success(self, client, mock_export_manager, tmp_path):
        # Setup: Create project directory
        project_name = "test_project"
        project_dir = tmp_path / "generated_projects" / "auto_agent_projects" / project_name
        project_dir.mkdir(parents=True)

        mock_export_manager.export_zip.return_value = tmp_path / "test.zip"

        response = client.post("/api/export/zip", json={"project_name": project_name})

        assert response.status_code == 200
        assert response.get_json()["success"] is True
        mock_export_manager.export_zip.assert_called_once()

    def test_export_zip_not_found(self, client):
        response = client.post("/api/export/zip", json={"project_name": "ghost"})
        assert response.status_code == 404
        assert "not found" in response.get_json()["error"]

    @patch("backend.utils.core.feedback.activity_report_generator.ActivityReportGenerator")
    def test_generate_report_success(self, mock_gen_cls, client):
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate_executive_report.return_value = "report.pdf"

        response = client.post("/api/export/report/my_proj")

        assert response.status_code == 200
        assert "success" in response.get_json()["status"]
        assert "report/my_proj.pdf" in response.get_json()["report_url"]

    def test_download_report_not_found(self, client):
        response = client.get("/api/export/report/missing.pdf")
        assert response.status_code == 404

    def test_deploy_github_success(self, client, mock_export_manager):
        mock_export_manager.deploy_to_github.return_value = "https://github.com/user/repo"

        payload = {"project_name": "p1", "token": "gh_token", "repo_name": "custom_repo"}

        response = client.post("/api/export/github", json=payload)

        assert response.status_code == 200
        assert response.get_json()["url"] == "https://github.com/user/repo"
        mock_export_manager.deploy_to_github.assert_called_once()

    def test_deploy_github_missing_token(self, client):
        response = client.post("/api/export/github", json={"project_name": "p1"})
        assert response.status_code == 400

    def test_get_targets_success(self, client, mock_export_manager):
        mock_export_manager.get_supported_targets.return_value = ["zip", "github"]

        response = client.get("/api/export/targets")

        assert response.status_code == 200
        assert "github" in response.get_json()["targets"]

    def test_manager_unavailable(self, app, client, monkeypatch):
        target_module = sys.modules["frontend.blueprints.export_bp"]
        monkeypatch.setattr(target_module, "_export_manager", None)

        response = client.post("/api/export/zip", json={"project_name": "any"})
        assert response.status_code == 503
