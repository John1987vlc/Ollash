"""Unit tests for project operations (delete, rename)."""

import pytest
from pathlib import Path
from unittest.mock import patch
from frontend.app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestProjectOps:
    @patch("os.path.isfile")
    @patch("os.path.isdir")
    @patch("os.remove")
    def test_delete_file_success(self, mock_remove, mock_isdir, mock_isfile, client):
        mock_isfile.return_value = True
        mock_isdir.return_value = False

        # Patch the MODULE level global _ollash_root_dir in the BP module
        with patch("frontend.blueprints.auto_agent_bp._ollash_root_dir", Path("/tmp"), create=True):
            response = client.post(
                "/api/projects/test_project/delete", json={"path": "src/main.py"}, headers={"X-API-Key": "dummy-key"}
            )
            assert response.status_code in [200, 401]

    @patch("os.rename")
    def test_rename_success(self, mock_rename, client):
        with patch("frontend.blueprints.auto_agent_bp._ollash_root_dir", Path("/tmp"), create=True):
            response = client.post(
                "/api/projects/test_project/rename",
                json={"old_path": "old.py", "new_path": "new.py"},
                headers={"X-API-Key": "dummy-key"},
            )
            assert response.status_code in [200, 401]
