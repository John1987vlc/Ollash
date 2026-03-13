import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_deps():
    deps = {
        "config": {},
        "logger": MagicMock(),
        "ollash_root_dir": Path("/tmp"),
        "llm_manager": MagicMock(),
        "response_parser": MagicMock(),
        "file_manager": MagicMock(),
        "file_validator": MagicMock(),
        "documentation_manager": MagicMock(),
        "event_publisher": MagicMock(),
        "code_quarantine": MagicMock(),
        "fragment_cache": MagicMock(),
        "dependency_graph": MagicMock(),
        "dependency_scanner": MagicMock(),
        "parallel_generator": MagicMock(),
        "error_knowledge_base": MagicMock(),
        "policy_enforcer": MagicMock(),
        "rag_context_selector": MagicMock(),
        "project_planner": MagicMock(),
        "structure_generator": MagicMock(),
        "file_content_generator": MagicMock(),
        "file_refiner": MagicMock(),
        "file_completeness_checker": MagicMock(),
        "project_reviewer": MagicMock(),
        "improvement_suggester": MagicMock(),
        "improvement_planner": MagicMock(),
        "senior_reviewer": MagicMock(),
        "test_generator": MagicMock(),
        "contingency_planner": MagicMock(),
        "structure_pre_reviewer": MagicMock(),
        "generated_projects_dir": Path("/tmp/projects"),
    }
    return deps


@pytest.fixture
def context(mock_deps):
    return PhaseContext(**mock_deps)


@pytest.mark.unit
def test_is_small_model_config_override_small(mock_deps):
    """model_size_overrides config entry forces nano-tier regardless of model name."""
    mock_deps["config"] = {"model_size_overrides": {"coder": 7}}
    ctx = PhaseContext(**mock_deps)
    assert ctx._is_small_model("coder") is True


@pytest.mark.unit
def test_is_small_model_config_override_large(mock_deps):
    """model_size_overrides with value >8 must NOT be treated as small model."""
    mock_deps["config"] = {"model_size_overrides": {"coder": 30}}
    ctx = PhaseContext(**mock_deps)
    assert ctx._is_small_model("coder") is False


@pytest.mark.unit
def test_is_mid_model_config_override(mock_deps):
    """model_size_overrides with mid-tier value is correctly detected by _is_mid_model."""
    mock_deps["config"] = {"model_size_overrides": {"coder": 14}}
    ctx = PhaseContext(**mock_deps)
    assert ctx._is_mid_model("coder") is True


def test_select_related_files_heuristic(context):
    generated_files = {
        "src/app.py": "content",
        "src/models.py": "content",
        "tests/test_app.py": "content",
        "README.md": "content",
    }
    # Should prefer models.py when looking for context for app.py
    # because it has 'model' in name and is in same dir.
    context.rag_context_selector.select_relevant_files.return_value = None  # Fallback to heuristic

    related = context.select_related_files("src/app.py", generated_files)
    assert "src/models.py" in related
    assert "README.md" in related


@pytest.mark.unit
async def test_implement_plan_create_file(context):
    plan = {"actions": [{"type": "create_file", "path": "new.txt", "content": "hello"}]}
    files = {}
    file_paths = []

    res_files, _, res_paths = await context.implement_plan(plan, Path("/tmp"), "readme", {}, files, file_paths)

    assert "new.txt" in res_files
    assert res_files["new.txt"] == "hello"
    assert "new.txt" in res_paths
    context.file_manager.write_file.assert_called()


@pytest.mark.unit
async def test_implement_plan_refine_file(context):
    plan = {"actions": [{"type": "refine_file", "path": "old.py", "issues": ["bug"]}]}
    files = {"old.py": "print(1)"}
    context.file_refiner.refine_file = AsyncMock(return_value="print(2)")

    res_files, _, _ = await context.implement_plan(plan, Path("/tmp"), "readme", {}, files, [])

    assert res_files["old.py"] == "print(2)"
    context.file_refiner.refine_file.assert_called_with("old.py", "print(1)", "readme", ["bug"])


# ---------------------------------------------------------------------------
# F3: build_api_map and _is_small_model
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_api_map_includes_py_file(context):
    py_content = "def hello():\n    return 'hi'\n"
    context.build_api_map({"src/main.py": py_content})
    assert "src/main.py" in context.api_map
    assert "hello" in context.api_map["src/main.py"]


@pytest.mark.unit
def test_build_api_map_excludes_md_file(context):
    context.build_api_map({"README.md": "# Title\nSome text"})
    assert "README.md" not in context.api_map


@pytest.mark.unit
def test_build_api_map_excludes_empty_content(context):
    context.build_api_map({"src/utils.py": ""})
    assert "src/utils.py" not in context.api_map


@pytest.mark.unit
def test_build_api_map_handles_multiple_types(context):
    files = {
        "a.py": "def foo(): pass",
        "b.ts": "export function bar(): void {}",
        "config.json": '{"key": "value"}',
    }
    context.build_api_map(files)
    assert "a.py" in context.api_map
    assert "b.ts" in context.api_map
    assert "config.json" not in context.api_map


@pytest.mark.unit
def test_build_api_map_clears_previous_entries(context):
    context.api_map["old.py"] = "old signature"
    context.build_api_map({"new.py": "def new(): pass"})
    assert "old.py" not in context.api_map
    assert "new.py" in context.api_map


@pytest.mark.unit
def test_is_small_model_3b_returns_true(context):
    mock_client = MagicMock()
    mock_client.model = "qwen3:3b"
    context.llm_manager.get_client.return_value = mock_client
    assert context._is_small_model("coder") is True


@pytest.mark.unit
def test_is_small_model_30b_returns_false(context):
    mock_client = MagicMock()
    mock_client.model = "qwen3-coder:30b"
    context.llm_manager.get_client.return_value = mock_client
    assert context._is_small_model("coder") is False


@pytest.mark.unit
def test_is_small_model_no_suffix_returns_false(context):
    mock_client = MagicMock()
    mock_client.model = "llama3"
    context.llm_manager.get_client.return_value = mock_client
    assert context._is_small_model("coder") is False


@pytest.mark.unit
def test_is_small_model_error_returns_false(context):
    context.llm_manager.get_client.side_effect = RuntimeError("no client")
    assert context._is_small_model("coder") is False
