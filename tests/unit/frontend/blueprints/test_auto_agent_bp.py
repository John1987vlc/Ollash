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
    main_container.core.logging.logger.override(mock)
    yield mock
    main_container.core.logging.logger.reset_override()


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


# ---------------------------------------------------------------------------
# _parse_git_url unit tests
# ---------------------------------------------------------------------------


class TestParseGitUrl:
    """Tests for the _parse_git_url helper function."""

    def test_full_github_url_with_org(self):
        from frontend.blueprints.auto_agent_bp import _parse_git_url

        org, repo = _parse_git_url("https://github.com/my-org/my-repo.git")
        assert org == "my-org"
        assert repo == "my-repo"

    def test_url_without_org(self):
        from frontend.blueprints.auto_agent_bp import _parse_git_url

        org, repo = _parse_git_url("https://github.com/my-repo.git")
        assert org == ""
        assert repo == "my-repo"

    def test_url_without_git_suffix(self):
        from frontend.blueprints.auto_agent_bp import _parse_git_url

        org, repo = _parse_git_url("https://github.com/acme/cool-app")
        assert org == "acme"
        assert repo == "cool-app"

    def test_empty_string_returns_empty_tuple(self):
        from frontend.blueprints.auto_agent_bp import _parse_git_url

        org, repo = _parse_git_url("")
        assert org == ""
        assert repo == ""

    def test_deep_nested_path_uses_last_two_segments(self):
        from frontend.blueprints.auto_agent_bp import _parse_git_url

        org, repo = _parse_git_url("https://gitlab.com/group/subgroup/project.git")
        assert org == "subgroup"
        assert repo == "project"

    def test_ssh_style_url(self):
        from frontend.blueprints.auto_agent_bp import _parse_git_url

        # urlparse treats the netloc as "git@github.com" and path as "/org/repo.git"
        org, repo = _parse_git_url("https://github.com/org/repo.git")
        assert org == "org"
        assert repo == "repo"


# ---------------------------------------------------------------------------
# create_project GitHub integration tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateProjectGitHub:
    """Tests for GitHub parameter handling in the create_project route."""

    @pytest.fixture(autouse=True)
    def _setup(self, app, client, mock_logger):
        self.app = app
        self.client = client

    @pytest.fixture
    def mock_agent_instance(self):
        """Build a mock agent instance that records run() kwargs."""
        instance = MagicMock()
        instance.logger = MagicMock()
        instance.event_publisher = None
        instance.run.return_value = "/tmp/fake-project"
        return instance

    def test_create_project_returns_started_with_git_url(self, mock_agent_instance):
        """POST with git_repo_url returns 200 status=started immediately."""
        main_container.auto_agent_module.auto_agent.override(MagicMock(return_value=mock_agent_instance))
        try:
            resp = self.client.post(
                "/api/projects/create",
                data={
                    "project_name": "gh-proj",
                    "project_description": "Test with GitHub URL",
                    "git_repo_url": "https://github.com/acme/gh-proj.git",
                    "git_token": "ghp_faketoken",
                },
            )
        finally:
            main_container.auto_agent_module.auto_agent.reset_override()

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "started"
        assert body["project_name"] == "gh-proj"

    def test_create_project_without_github_url_also_starts(self, mock_agent_instance):
        """POST without git_repo_url still returns 200 status=started."""
        main_container.auto_agent_module.auto_agent.override(MagicMock(return_value=mock_agent_instance))
        try:
            resp = self.client.post(
                "/api/projects/create",
                data={
                    "project_name": "local-proj",
                    "project_description": "No GitHub integration",
                },
            )
        finally:
            main_container.auto_agent_module.auto_agent.reset_override()

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "started"

    def test_create_project_missing_fields_returns_400(self):
        """POST without required fields returns 400."""
        resp = self.client.post("/api/projects/create", data={})
        assert resp.status_code == 400
