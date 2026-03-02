"""Unit tests for NanoTaskExpander — per-function task decomposition for ≤8B models."""

import pytest

from backend.agents.auto_agent_phases.nano_task_expander import NanoTaskExpander


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_task(**overrides):
    t = {
        "id": "TASK-001",
        "title": "Implement src/utils.py",
        "description": "Build utility functions",
        "file_path": "src/utils.py",
        "task_type": "implement_function",
        "dependencies": [],
        "context_files": [],
        "logic_plan": {},
    }
    t.update(overrides)
    return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNanoTaskExpanderExpand:
    def test_unsupported_extension_returns_empty(self):
        task = _base_task(file_path="Makefile")
        assert NanoTaskExpander.expand(task, "") == []

    def test_unsupported_extension_yaml_returns_empty(self):
        task = _base_task(file_path="config.yaml")
        assert NanoTaskExpander.expand(task, "key: value") == []

    def test_python_stubs_extracted(self):
        content = "def add(x: int, y: int) -> int:\n    pass\n\ndef subtract(x: int, y: int) -> int:\n    pass\n"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert len(tasks) == 2
        names = {t["function_name"] for t in tasks}
        assert names == {"add", "subtract"}

    def test_private_functions_excluded(self):
        content = "def _helper(): pass\ndef public_func(): pass\n"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        names = [t["function_name"] for t in tasks]
        assert "_helper" not in names
        assert "public_func" in names

    def test_implemented_functions_excluded(self):
        """Functions with a real body (not just pass) must not be expanded."""
        content = "def real_func():\n    x = 1\n    return x\n"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert tasks == []

    def test_stub_with_docstring_is_still_a_stub(self):
        content = 'def greet(name: str) -> str:\n    """Return greeting."""\n    pass\n'
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert len(tasks) == 1
        assert tasks[0]["function_name"] == "greet"
        assert "Return greeting" in tasks[0]["function_docstring"]

    def test_ids_are_sub_ids_of_parent(self):
        content = "def foo(): pass\ndef bar(): pass\n"
        tasks = NanoTaskExpander.expand(_base_task(id="TASK-007"), content)
        assert tasks[0]["id"] == "TASK-007-N00"
        assert tasks[1]["id"] == "TASK-007-N01"

    def test_nano_subtask_flag_is_set(self):
        content = "def foo(): pass\n"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert tasks[0]["is_nano_subtask"] is True

    def test_task_type_remains_implement_function(self):
        content = "def foo(): pass\n"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert tasks[0]["task_type"] == "implement_function"

    def test_file_path_preserved_in_sub_tasks(self):
        content = "def foo(): pass\n"
        tasks = NanoTaskExpander.expand(_base_task(file_path="src/utils.py"), content)
        assert tasks[0]["file_path"] == "src/utils.py"

    def test_dependency_chain(self):
        content = "def a(): pass\ndef b(): pass\ndef c(): pass\n"
        tasks = NanoTaskExpander.expand(_base_task(id="TASK-001", dependencies=["TASK-000"]), content)
        # First sub-task inherits parent dependencies
        assert tasks[0]["dependencies"] == ["TASK-000"]
        # Subsequent sub-tasks chain on previous
        assert tasks[1]["dependencies"] == ["TASK-001-N00"]
        assert tasks[2]["dependencies"] == ["TASK-001-N01"]

    def test_context_files_inherited(self):
        content = "def foo(): pass\n"
        ctx_files = ["models.py", "config.py"]
        tasks = NanoTaskExpander.expand(_base_task(context_files=ctx_files), content)
        assert tasks[0]["context_files"] == ctx_files

    def test_fallback_to_exports_when_no_content(self):
        task = _base_task(logic_plan={"exports": ["compute", "validate"]})
        tasks = NanoTaskExpander.expand(task, "")
        assert len(tasks) == 2
        names = [t["function_name"] for t in tasks]
        assert "compute" in names
        assert "validate" in names

    def test_fallback_exports_private_filtered(self):
        task = _base_task(logic_plan={"exports": ["_private", "public_fn"]})
        tasks = NanoTaskExpander.expand(task, "")
        names = [t["function_name"] for t in tasks]
        assert "_private" not in names
        assert "public_fn" in names

    def test_returns_empty_when_no_stubs_and_no_exports(self):
        tasks = NanoTaskExpander.expand(_base_task(), "")
        assert tasks == []

    def test_returns_empty_when_content_has_no_stubs_and_no_exports(self):
        content = "x = 1\ny = 2\n"  # No functions at all
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert tasks == []

    def test_async_functions_extracted(self):
        content = "async def fetch_data(url: str) -> dict:\n    pass\n"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert len(tasks) == 1
        assert tasks[0]["function_name"] == "fetch_data"
        assert "async def" in tasks[0]["function_signature"]

    def test_syntax_error_content_returns_empty(self):
        """Malformed Python should not raise — return empty list."""
        content = "def broken(\n    pass"
        tasks = NanoTaskExpander.expand(_base_task(), content)
        assert tasks == []  # SyntaxError is swallowed
