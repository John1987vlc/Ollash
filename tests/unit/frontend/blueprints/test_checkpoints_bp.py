import pytest
from unittest.mock import MagicMock
import sys
from flask import Flask

# Import the blueprint
from frontend.blueprints.checkpoints_bp import checkpoints_bp


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a Flask app for testing checkpoint endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True})

    # Access the module directly to patch global/module imports
    target_module = sys.modules["frontend.blueprints.checkpoints_bp"]

    # Mock the container
    mock_container = MagicMock()
    mock_container.core.ollash_root_dir.return_value = tmp_path
    monkeypatch.setattr(target_module, "main_container", mock_container)

    # Mock StructuredLogger to avoid real log file creation
    monkeypatch.setattr(target_module, "StructuredLogger", MagicMock())

    app.register_blueprint(checkpoints_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def mock_checkpoint_manager(monkeypatch):
    """Mock the CheckpointManager class in the blueprint module."""
    target_module = sys.modules["frontend.blueprints.checkpoints_bp"]
    mock_mgr_cls = MagicMock()
    mock_mgr_instance = mock_mgr_cls.return_value
    monkeypatch.setattr(target_module, "CheckpointManager", mock_mgr_cls)
    return mock_mgr_instance


class TestCheckpointsBlueprint:
    """Test suite for Project Checkpoints management endpoints."""

    def test_list_checkpoints_success(self, client, mock_checkpoint_manager):
        mock_checkpoints = ["phase_1_init", "phase_2_plan"]
        mock_checkpoint_manager.list_checkpoints.return_value = mock_checkpoints

        response = client.get("/api/checkpoints/my_project")

        assert response.status_code == 200
        data = response.get_json()
        assert data["checkpoints"] == mock_checkpoints
        mock_checkpoint_manager.list_checkpoints.assert_called_with("my_project")

    def test_restore_checkpoint_success(self, client, mock_checkpoint_manager, tmp_path):
        # Setup mock checkpoint with some files
        mock_checkpoint = MagicMock()
        mock_checkpoint.generated_files = {"main.py": "print('hello')", "utils/helper.py": "def test(): pass"}
        mock_checkpoint_manager.load_at_phase.return_value = mock_checkpoint

        project_name = "test_restore"
        response = client.post("/api/checkpoints/restore", json={"project_name": project_name, "phase_name": "phase_2"})

        assert response.status_code == 200
        assert response.get_json()["status"] == "restored"

        # Verify files were actually written to tmp_path
        project_dir = tmp_path / "generated_projects" / "auto_agent_projects" / project_name
        assert (project_dir / "main.py").read_text() == "print('hello')"
        assert (project_dir / "utils" / "helper.py").read_text() == "def test(): pass"

    def test_restore_checkpoint_not_found(self, client, mock_checkpoint_manager):
        mock_checkpoint_manager.load_at_phase.return_value = None

        response = client.post("/api/checkpoints/restore", json={"project_name": "unknown", "phase_name": "phase_1"})

        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_restore_checkpoint_no_payload(self, client):
        # Missing project_name/phase_name in payload might cause AttributeError or similar
        # depending on implementation, but let's check it doesn't crash 500
        response = client.post("/api/checkpoints/restore", json={})
        # Current implementation would try to load with None, which would return None from mgr
        assert response.status_code == 404
