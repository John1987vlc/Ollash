import pytest
from unittest.mock import MagicMock
from backend.utils.domains.git.git_operations_tools import GitOperationsTools


class TestGitToolsUnit:
    """
    Unit tests for GitOperationsTools to ensure inputs/outputs are correct.
    """

    @pytest.fixture
    def mock_deps(self):
        executor = MagicMock()
        executor.auto_confirm_minor_git_commits = True
        executor.git_auto_confirm_lines_threshold = 10
        executor.critical_paths_patterns = []

        return {"git_manager": MagicMock(), "logger": MagicMock(), "tool_executor": executor}

    @pytest.fixture
    def git_tools(self, mock_deps):
        return GitOperationsTools(
            git_manager=mock_deps["git_manager"], logger=mock_deps["logger"], tool_executor=mock_deps["tool_executor"]
        )

    def test_git_status_success(self, git_tools, mock_deps):
        """Validates git_status delegation."""
        mock_deps["git_manager"].current_branch.return_value = "main"

        result = git_tools.git_status()

        assert result["ok"] is True
        assert result["branch"] == "main"
        mock_deps["git_manager"].current_branch.assert_called_once()

    def test_git_commit_no_confirm(self, git_tools, mock_deps):
        """Validates git_commit with minor changes."""
        # Mock diff stats
        mock_deps["git_manager"].diff_numstat.return_value = {"success": True, "total": 5, "files": ["file.py"]}
        mock_deps["git_manager"].create_commit_with_all.return_value = {"success": True}

        result = git_tools.git_commit("feat: test")

        assert result["ok"] is True
        mock_deps["git_manager"].create_commit_with_all.assert_called_once_with("feat: test")
