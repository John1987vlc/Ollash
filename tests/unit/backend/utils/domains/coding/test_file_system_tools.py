import pytest
from unittest.mock import MagicMock
from backend.utils.domains.code.file_system_tools import FileSystemTools


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_file_manager():
    return MagicMock()


@pytest.fixture
def mock_confirmation_manager():
    mock = MagicMock()
    mock.critical_paths_patterns = []
    mock.auto_confirm_minor_writes = False
    mock.write_auto_confirm_lines_threshold = 5
    mock._ask_confirmation.return_value = True
    return mock


@pytest.fixture
def tools(tmp_path, mock_file_manager, mock_logger, mock_confirmation_manager):
    return FileSystemTools(
        project_root=tmp_path,
        file_manager=mock_file_manager,
        logger=mock_logger,
        tool_executor=mock_confirmation_manager,
    )


class TestFileSystemTools:
    """Test suite for specialized file system domain tools."""

    def test_read_file_success(self, tools, tmp_path):
        (tmp_path / "test.txt").write_text("line1\nline2\nline3")

        result = tools.read_file("test.txt", offset=0, limit=2)

        assert result["ok"] is True
        assert result["content"] == "line1\nline2"
        assert result["total_lines"] == 3
        assert result["reads"] == 1

    def test_read_file_not_found(self, tools):
        result = tools.read_file("missing.txt")
        assert result["ok"] is False
        assert result["error"] == "not_found"

    def test_write_file_new_success(self, tools, tmp_path, mock_confirmation_manager):
        result = tools.write_file("new.txt", "hello", reason="testing")

        assert result["ok"] is True
        assert (tmp_path / "new.txt").read_text() == "hello"
        mock_confirmation_manager._ask_confirmation.assert_called_once()

    def test_write_file_user_cancelled(self, tools, mock_confirmation_manager):
        mock_confirmation_manager._ask_confirmation.return_value = False

        result = tools.write_file("cancel.txt", "no", reason="fail")

        assert result["ok"] is False
        assert result["error"] == "user_cancelled"

    def test_delete_file_success(self, tools, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("bye")

        result = tools.delete_file("del.txt", reason="cleanup")

        assert result["ok"] is True
        assert not f.exists()

    def test_summarize_file(self, tools, tmp_path):
        (tmp_path / "code.py").write_text("import os\nclass A:\n    def b(self): pass")

        result = tools.summarize_file("code.py")

        assert result["ok"] is True
        assert result["lines"] == 3
        assert result["classes"] == 1
        assert result["functions"] == 1
        assert result["imports"] == 1

    def test_list_directory(self, tools, tmp_path):
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "dir").mkdir()

        result = tools.list_directory(".")
        assert result["ok"] is True
        assert result["count"] == 2
        assert "a.txt" in result["items"]
