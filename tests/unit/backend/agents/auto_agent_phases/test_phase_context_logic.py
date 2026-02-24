import pytest
from pathlib import Path
from unittest.mock import MagicMock
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
        "generated_projects_dir": Path("/tmp/projects")
    }
    return deps

@pytest.fixture
def context(mock_deps):
    return PhaseContext(**mock_deps)

def test_select_related_files_heuristic(context):
    generated_files = {
        "src/app.py": "content",
        "src/models.py": "content",
        "tests/test_app.py": "content",
        "README.md": "content"
    }
    # Should prefer models.py when looking for context for app.py
    # because it has 'model' in name and is in same dir.
    context.rag_context_selector.select_relevant_files.return_value = None # Fallback to heuristic

    related = context.select_related_files("src/app.py", generated_files)
    assert "src/models.py" in related
    assert "README.md" in related

def test_implement_plan_create_file(context):
    plan = {
        "actions": [
            {"type": "create_file", "path": "new.txt", "content": "hello"}
        ]
    }
    files = {}
    file_paths = []

    res_files, _, res_paths = context.implement_plan(plan, Path("/tmp"), "readme", {}, files, file_paths)

    assert "new.txt" in res_files
    assert res_files["new.txt"] == "hello"
    assert "new.txt" in res_paths
    context.file_manager.write_file.assert_called()

def test_implement_plan_refine_file(context):
    plan = {
        "actions": [
            {"type": "refine_file", "path": "old.py", "issues": ["bug"]}
        ]
    }
    files = {"old.py": "print(1)"}
    context.file_refiner.refine_file.return_value = "print(2)"

    res_files, _, _ = context.implement_plan(plan, Path("/tmp"), "readme", {}, files, [])

    assert res_files["old.py"] == "print(2)"
    context.file_refiner.refine_file.assert_called_with("old.py", "print(1)", "readme", ["bug"])
