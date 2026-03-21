"""Unit tests for ProjectCreationTools."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.utils.domains.auto_generation.tools.project_creation_tools import ProjectCreationTools


def _make_tools(tmp_path: Path, on_blueprint_ready=None) -> ProjectCreationTools:
    return ProjectCreationTools(
        project_root=tmp_path / "project",
        event_publisher=MagicMock(),
        logger=MagicMock(),
        on_blueprint_ready=on_blueprint_ready,
        orchestrator_model="ministral-3:8b",
        code_model="qwen3.5:9b",
    )


@pytest.mark.unit
class TestProjectCreationToolsSafePath:
    def test_safe_path_allows_valid_relative(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = tools._safe_path("src/main.py")
        assert result == (tmp_path / "project" / "src" / "main.py").resolve()

    def test_safe_path_raises_on_traversal(self, tmp_path):
        tools = _make_tools(tmp_path)
        with pytest.raises(ValueError, match="Path traversal"):
            tools._safe_path("../../etc/passwd")

    def test_safe_path_raises_on_absolute(self, tmp_path):
        tools = _make_tools(tmp_path)
        with pytest.raises(ValueError, match="Path traversal"):
            tools._safe_path("/etc/passwd")


@pytest.mark.unit
class TestPlanProject:
    async def test_plan_project_valid_blueprint(self, tmp_path):
        tools = _make_tools(tmp_path)
        blueprint = {
            "project_type": "api",
            "tech_stack": ["python", "fastapi"],
            "files": [{"path": "main.py", "purpose": "entry point"}],
        }
        result = await tools.plan_project(json.dumps(blueprint))

        assert result["ok"] is True
        assert result["files_planned"] == 1
        assert result["project_type"] == "api"
        assert result["tech_stack"] == ["python", "fastapi"]
        assert tools._blueprint == blueprint

    async def test_plan_project_invalid_json(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = await tools.plan_project("not valid json {{{")
        assert result["ok"] is False
        assert "Invalid JSON" in result["error"]

    async def test_plan_project_non_dict_json(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = await tools.plan_project("[1, 2, 3]")
        assert result["ok"] is False
        assert "JSON object" in result["error"]

    async def test_plan_project_callback_abort(self, tmp_path):
        callback = MagicMock(return_value=False)
        tools = _make_tools(tmp_path, on_blueprint_ready=callback)
        result = await tools.plan_project('{"project_type":"api","files":[]}')
        assert result["ok"] is False
        assert "aborted" in result["error"]
        assert tools._aborted is True

    async def test_plan_project_callback_continue(self, tmp_path):
        callback = MagicMock(return_value=True)
        tools = _make_tools(tmp_path, on_blueprint_ready=callback)
        result = await tools.plan_project('{"project_type":"api","files":[]}')
        assert result["ok"] is True
        callback.assert_called_once()

    async def test_plan_project_creates_directory(self, tmp_path):
        tools = _make_tools(tmp_path)
        await tools.plan_project('{"project_type":"api","files":[]}')
        assert (tmp_path / "project").is_dir()


@pytest.mark.unit
class TestWriteProjectFile:
    async def test_write_creates_file(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        result = await tools.write_project_file("main.py", "print('hello')")
        assert result["ok"] is True
        assert (tmp_path / "project" / "main.py").read_text() == "print('hello')"

    async def test_write_creates_subdirectory(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        result = await tools.write_project_file("src/utils.py", "# utils")
        assert result["ok"] is True
        assert (tmp_path / "project" / "src" / "utils.py").is_file()

    async def test_write_records_byte_count(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        content = "hello world"
        await tools.write_project_file("hello.txt", content)
        assert "hello.txt" in tools._files_written
        assert tools._files_written["hello.txt"] == len(content.encode("utf-8"))

    async def test_write_rejects_traversal(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = await tools.write_project_file("../../evil.py", "evil")
        assert result["ok"] is False
        assert "traversal" in result["error"].lower()


@pytest.mark.unit
class TestReadProjectFile:
    async def test_read_existing_file(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        (tools.project_root / "main.py").write_text("# hello", encoding="utf-8")
        result = await tools.read_project_file("main.py")
        assert result["ok"] is True
        assert result["content"] == "# hello"

    async def test_read_missing_file(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        result = await tools.read_project_file("missing.py")
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_read_rejects_traversal(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = await tools.read_project_file("../../secret.txt")
        assert result["ok"] is False


@pytest.mark.unit
class TestListProjectFiles:
    async def test_list_empty_project(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = await tools.list_project_files()
        assert result["ok"] is True
        assert result["files"] == []

    async def test_list_files_in_project(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        (tools.project_root / "main.py").write_text("# main", encoding="utf-8")
        (tools.project_root / "utils.py").write_text("# utils", encoding="utf-8")
        result = await tools.list_project_files()
        assert result["ok"] is True
        paths = [f["path"] for f in result["files"]]
        assert "main.py" in paths
        assert "utils.py" in paths

    async def test_list_skips_pycache(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        (tools.project_root / "__pycache__").mkdir()
        (tools.project_root / "__pycache__" / "main.cpython-310.pyc").write_bytes(b"")
        (tools.project_root / "main.py").write_text("# main", encoding="utf-8")
        result = await tools.list_project_files()
        paths = [f["path"] for f in result["files"]]
        assert not any("__pycache__" in p for p in paths)
        assert "main.py" in paths


@pytest.mark.unit
class TestRunLinter:
    async def test_linter_file_not_found(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        result = await tools.run_linter("nonexistent.py")
        assert result["ok"] is False
        assert "not found" in result["error"]

    async def test_linter_unknown_extension(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        (tools.project_root / "config.yaml").write_text("key: value", encoding="utf-8")
        result = await tools.run_linter("config.yaml")
        assert result["ok"] is True
        assert result["error_count"] == 0
        assert "No linter" in result.get("note", "")

    async def test_linter_rejects_traversal(self, tmp_path):
        tools = _make_tools(tmp_path)
        result = await tools.run_linter("../../evil.py")
        assert result["ok"] is False


@pytest.mark.unit
class TestGenerateInfrastructure:
    async def test_creates_python_gitignore(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        tools._files_written = {"main.py": 100, "utils.py": 50}
        result = await tools.generate_infrastructure()
        assert result["ok"] is True
        assert ".gitignore" in result["files_created"]
        gitignore = (tools.project_root / ".gitignore").read_text()
        assert "__pycache__" in gitignore

    async def test_creates_requirements_txt_for_python(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        tools._files_written = {"main.py": 100}
        result = await tools.generate_infrastructure()
        assert "requirements.txt" in result["files_created"]

    async def test_creates_dockerfile_for_python(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        tools._files_written = {"main.py": 100}
        result = await tools.generate_infrastructure()
        assert "Dockerfile" in result["files_created"]

    async def test_creates_package_json_for_node(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        tools._files_written = {"index.ts": 100, "utils.ts": 50}
        result = await tools.generate_infrastructure()
        assert result["ok"] is True
        assert "package.json" in result["files_created"]

    async def test_does_not_overwrite_existing_files(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        # Pre-create files
        (tools.project_root / ".gitignore").write_text("existing", encoding="utf-8")
        tools._files_written = {"main.py": 100}
        await tools.generate_infrastructure()
        # Should not have overwritten
        assert (tools.project_root / ".gitignore").read_text() == "existing"


@pytest.mark.unit
class TestFinishProject:
    async def test_finish_sets_finished_flag(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        result = await tools.finish_project("A simple API was built.")
        assert result["ok"] is True
        assert tools.finished is True

    async def test_finish_creates_readme(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        await tools.finish_project("A test project.")
        assert (tools.project_root / "README.md").is_file()

    async def test_finish_creates_ollash_md(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        await tools.finish_project("A test project.")
        ollash = (tools.project_root / "OLLASH.md").read_text()
        assert "AutoAgentWithTools" in ollash
        assert "ministral-3:8b" in ollash

    async def test_finish_returns_file_count(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        tools._files_written = {"main.py": 100, "utils.py": 50}
        result = await tools.finish_project("Done.")
        assert result["files_total"] == 2

    async def test_finish_does_not_overwrite_existing_readme(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools.project_root.mkdir(parents=True)
        (tools.project_root / "README.md").write_text("# custom", encoding="utf-8")
        await tools.finish_project("Done.")
        assert (tools.project_root / "README.md").read_text() == "# custom"


@pytest.mark.unit
class TestStateHint:
    def test_hint_before_plan(self, tmp_path):
        tools = _make_tools(tmp_path)
        hint = tools.state_hint()
        assert "plan_project" in hint

    def test_hint_with_remaining_files(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools._blueprint = {"files": [{"path": "main.py"}, {"path": "utils.py"}]}
        tools._files_written = {}
        hint = tools.state_hint()
        assert "main.py" in hint

    def test_hint_all_files_written(self, tmp_path):
        tools = _make_tools(tmp_path)
        tools._blueprint = {"files": [{"path": "main.py"}]}
        tools._files_written = {"main.py": 100}
        hint = tools.state_hint()
        assert "finish_project" in hint

    def test_hint_tool_definitions_has_all_tools(self, tmp_path):
        tool_names = {t["function"]["name"] for t in ProjectCreationTools.TOOL_DEFINITIONS}
        expected = {
            "plan_project",
            "write_project_file",
            "read_project_file",
            "list_project_files",
            "run_linter",
            "run_project_tests",
            "generate_infrastructure",
            "finish_project",
        }
        assert tool_names == expected
