import pytest
from unittest.mock import MagicMock
from backend.utils.domains.code.file_system_tools import FileSystemTools

class TestFileSystemToolsUnit:
    """
    Unit tests for FileSystemTools to ensure inputs/outputs are correct.
    """

    @pytest.fixture
    def mock_deps(self, tmp_path):
        executor = MagicMock()
        executor.critical_paths_patterns = []
        executor.auto_confirm_minor_writes = True
        executor.write_auto_confirm_lines_threshold = 10

        return {
            "file_manager": MagicMock(),
            "logger": MagicMock(),
            "tool_executor": executor,
            "tmp_path": tmp_path
        }

    @pytest.fixture
    def fs_tools(self, mock_deps):
        # We use real project_root for path math, but mock managers
        tools = FileSystemTools(
            project_root=mock_deps["tmp_path"],
            file_manager=mock_deps["file_manager"],
            logger=mock_deps["logger"],
            tool_executor=mock_deps["tool_executor"]
        )
        return tools

    def test_read_file_success(self, fs_tools, mock_deps):
        """Validates read_file (uses Path.read_text internally, not file_manager)."""
        test_file = mock_deps["tmp_path"] / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        result = fs_tools.read_file("test.txt")

        assert result["ok"] is True
        assert result["content"] == "hello world"

    def test_write_file_no_confirm_needed(self, fs_tools, mock_deps):
        """Validates write_file logic when changes are minor."""
        # Minor change (1 line) should NOT trigger request_confirmation if threshold is 10
        mock_deps["tool_executor"].request_confirmation = MagicMock(return_value=True)

        result = fs_tools.write_file("new.txt", "line1", "creating file")

        assert result["ok"] is True
        # Verify it actually wrote to disk (FileSystemTools writes directly)
        assert (mock_deps["tmp_path"] / "new.txt").read_text() == "line1"

    def test_list_directory_structure(self, fs_tools, mock_deps):
        """Validates directory listing output format."""
        (mock_deps["tmp_path"] / "subdir").mkdir()
        (mock_deps["tmp_path"] / "file.txt").touch()

        result = fs_tools.list_directory(".")

        assert result["ok"] is True
        assert "file.txt" in result["items"]
        assert "subdir" in result["items"]
