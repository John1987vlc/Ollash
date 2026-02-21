import pytest
from unittest.mock import MagicMock
from backend.utils.domains.code.code_analysis_tools import CodeAnalysisTools
from backend.utils.core.command_executor import ExecutionResult


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_analyzer():
    return MagicMock()


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.fixture
def tools(tmp_path, mock_analyzer, mock_executor, mock_logger):
    return CodeAnalysisTools(
        project_root=tmp_path, code_analyzer=mock_analyzer, command_executor=mock_executor, logger=mock_logger
    )


class TestCodeAnalysisTools:
    """Test suite for specialized code analysis domain tools."""

    def test_analyze_project_structure(self, tools, tmp_path):
        # Setup: Create some files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("print(1)")
        (tmp_path / "requirements.txt").write_text("flask\nrequests")
        (tmp_path / "__init__.py").write_text("")

        result = tools.analyze_project(focus="all")

        assert result["ok"] is True
        analysis = result["analysis"]
        assert analysis["structure"]["python_files"] == 2
        assert "src" in analysis["structure"]["top_level_dirs"]
        assert "flask" in analysis["dependencies"]
        assert analysis["signals"]["is_package"] is True

    def test_analyze_project_focus_dependencies(self, tools, tmp_path):
        (tmp_path / "requirements.txt").write_text("numpy")

        # Should only have dependencies if focus is dependencies
        result = tools.analyze_project(focus="dependencies")

        assert "dependencies" in result["analysis"]
        assert "structure" not in result["analysis"]
        assert result["analysis"]["dependencies"] == ["numpy"]

    def test_search_code_success(self, tools, mock_executor):
        mock_res = ExecutionResult(
            success=True,
            stdout="src/main.py:10:def hello():\nsrc/utils.py:5:def hello():",
            stderr="",
            return_code=0,
            command="grep",
        )
        mock_executor.execute.return_value = mock_res

        result = tools.search_code(query="def hello")

        assert result["ok"] is True
        assert len(result["matches"]) == 2
        assert "src/main.py" in result["matches"][0]
        mock_executor.execute.assert_called_once()

    def test_search_code_failure(self, tools, mock_executor):
        mock_res = ExecutionResult(False, "", "grep error", 1, "grep")
        mock_executor.execute.return_value = mock_res

        result = tools.search_code(query="invalid")

        assert result["ok"] is False
        assert "grep error" in result["error"]
