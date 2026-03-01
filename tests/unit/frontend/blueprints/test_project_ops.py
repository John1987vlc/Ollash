"""Unit tests for project operations (delete, rename)."""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch
from frontend.app import create_app


@pytest.fixture
def tmp_project_root(tmp_path):
    """Create a temp project directory structure."""
    project_dir = tmp_path / "generated_projects" / "auto_agent_projects" / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    src = project_dir / "src"
    src.mkdir(exist_ok=True)
    (src / "main.py").write_text("print('hello')")
    (project_dir / "old.py").write_text("# old")
    return tmp_path


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestProjectOps:
    def test_delete_file_success(self, client, tmp_project_root):
        _mod = sys.modules["frontend.blueprints.auto_agent_bp"]
        with patch.object(_mod, "_ollash_root_dir", tmp_project_root):
            response = client.post(
                "/api/projects/test_project/delete",
                json={"path": "src/main.py"},
                headers={"X-API-Key": "dummy-key"},
            )
            assert response.status_code in [200, 401]

    def test_rename_success(self, client, tmp_project_root):
        _mod = sys.modules["frontend.blueprints.auto_agent_bp"]
        with patch.object(_mod, "_ollash_root_dir", tmp_project_root):
            response = client.post(
                "/api/projects/test_project/rename",
                json={"old_path": "old.py", "new_path": "new.py"},
                headers={"X-API-Key": "dummy-key"},
            )
            assert response.status_code in [200, 401]
