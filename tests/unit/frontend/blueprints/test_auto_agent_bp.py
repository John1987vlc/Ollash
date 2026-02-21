import pytest
from unittest.mock import MagicMock, patch
import sys
from flask import Flask

# Import the blueprint and its initialization
from frontend.blueprints.auto_agent_bp import auto_agent_bp, init_app
from backend.core.containers import main_container


@pytest.fixture
def test_root(tmp_path):
    """Create a real temporary root structure for tests."""
    root = tmp_path / "ollash_root"
    projects_dir = root / "generated_projects" / "auto_agent_projects"
    projects_dir.mkdir(parents=True)
    return root


@pytest.fixture
def app(test_root):
    """Create and configure a new app instance with a real temp root."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": test_root, "SECRET_KEY": "test_secret"})

    # Mock services needed by init_app
    mock_publisher = MagicMock()
    mock_bridge = MagicMock()

    # Initialize blueprint
    init_app(app, mock_publisher, mock_bridge)
    app.register_blueprint(auto_agent_bp)

    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def mock_agent():
    """Override the AutoAgent provider in the DI container."""
    mock = MagicMock()
    main_container.auto_agent_module.auto_agent.override(mock)
    yield mock
    main_container.auto_agent_module.auto_agent.reset_override()


@pytest.fixture
def mock_logger():
    """Override the core logger provider."""
    mock = MagicMock()
    main_container.core.logger.override(mock)
    yield mock
    main_container.core.logger.reset_override()


class TestAutoAgentBlueprint:
    """Test suite for AutoAgent Blueprint with real temp filesystem and DI isolation."""

    def test_generate_structure_success(self, client, mock_agent):
        mock_agent.generate_structure_only.return_value = ("# README", {"src": {}})
        response = client.post(
            "/api/projects/generate_structure",
            data={"project_description": "A test project", "project_name": "test_proj"},
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "structure_generated"

    def test_list_all_projects_populated(self, client, test_root):
        """Test listing using real temp directories."""
        projects_dir = test_root / "generated_projects" / "auto_agent_projects"
        (projects_dir / "proj1").mkdir()
        (projects_dir / "proj2").mkdir()

        response = client.get("/api/projects/list")
        assert response.status_code == 200
        projects = response.get_json()["projects"]
        assert "proj1" in projects
        assert "proj2" in projects

    def test_read_file_content_success(self, client, test_root):
        """Test reading a real temp file."""
        project_path = test_root / "generated_projects" / "auto_agent_projects" / "myproj"
        project_path.mkdir(parents=True)
        file_path = project_path / "README.md"
        file_path.write_text("hello testing", encoding="utf-8")

        response = client.post("/api/projects/myproj/file", json={"file_path_relative": "README.md"})
        assert response.status_code == 200
        assert response.get_json()["content"] == "hello testing"

    def test_export_project_zip(self, client, test_root, app, monkeypatch):
        """Test ZIP export logic by using monkeypatch on the specific module namespace from sys.modules."""
        project_path = test_root / "generated_projects" / "auto_agent_projects" / "myproj"
        project_path.mkdir(parents=True)
        (project_path / "main.py").write_text("print('hi')")

        mock_send = MagicMock(return_value=app.response_class("fake-zip-data", status=200))
        # Ensure we target the actual module, avoiding any blueprint name collision
        target_module = sys.modules["frontend.blueprints.auto_agent_bp"]
        monkeypatch.setattr(target_module, "send_file", mock_send)

        response = client.get("/api/projects/myproj/export")
        assert response.status_code == 200
        assert response.data.decode() == "fake-zip-data"
        mock_send.assert_called_once()

    def test_delete_project_item(self, client, test_root):
        """Test actual file deletion in temp root."""
        project_path = test_root / "generated_projects" / "auto_agent_projects" / "myproj"
        project_path.mkdir(parents=True)
        temp_file = project_path / "temp.txt"
        temp_file.write_text("delete me")

        response = client.post("/api/projects/myproj/delete", json={"path": "temp.txt"})
        assert response.status_code == 200
        assert not temp_file.exists()

    @patch("backend.utils.core.analysis.input_validators.validate_git_url", return_value=True)
    @patch("backend.utils.core.analysis.input_validators.validate_project_name", return_value=True)
    @patch("subprocess.run")
    def test_clone_project_success(self, mock_run, mock_vname, mock_vurl, client, test_root, mock_logger):
        """Test git clone logic construction."""
        mock_run.return_value = MagicMock(returncode=0)
        response = client.post(
            "/api/projects/clone", data={"git_url": "https://github.com/user/repo.git", "project_name": "cloned_repo"}
        )
        assert response.status_code == 200
        # Assert that the fourth argument of the first call (target path) is correct
        called_args = mock_run.call_args[0][0]
        assert called_args[3] == str(test_root / "generated_projects" / "auto_agent_projects" / "cloned_repo")
