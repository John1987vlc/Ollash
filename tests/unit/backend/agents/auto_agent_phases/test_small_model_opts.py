"""Unit tests for the 6 small-model optimizations (Opt 1–3 + gating).

Tests cover:
- _opt_enabled() gating logic (Steps 1)
- build_micro_context_snapshot() (Opt 2)
- _check_output_contract() (Opt 3)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_deps(**overrides):
    base = {
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
    base.update(overrides)
    return base


@pytest.fixture
def small_model_context():
    """PhaseContext whose coder client reports a 3B model."""
    deps = _make_deps()
    ctx = PhaseContext(**deps)
    client_mock = MagicMock()
    client_mock.model = "ministral-3:3b"
    ctx.llm_manager.get_client.return_value = client_mock
    ctx.config = {
        "small_model_optimizations": {
            "opt1_prompt_state_machine": True,
            "opt2_micro_context_snapshot": True,
            "opt3_exit_contract": True,
            "opt4_incremental_backlog": True,
            "opt5_anti_pattern_injection": True,
            "opt6_active_shadow": True,
        }
    }
    return ctx


@pytest.fixture
def large_model_context():
    """PhaseContext whose coder client reports a 30B model."""
    deps = _make_deps()
    ctx = PhaseContext(**deps)
    client_mock = MagicMock()
    client_mock.model = "qwen3-coder:30b"
    ctx.llm_manager.get_client.return_value = client_mock
    ctx.config = {
        "small_model_optimizations": {
            "opt1_prompt_state_machine": True,
            "opt2_micro_context_snapshot": True,
        }
    }
    return ctx


@pytest.fixture
def phase(small_model_context):
    return FileContentGenerationPhase(small_model_context)


# ---------------------------------------------------------------------------
# Tests: _opt_enabled()
# ---------------------------------------------------------------------------


class TestOptEnabled:
    @pytest.mark.unit
    def test_small_model_flag_true_returns_true(self, small_model_context):
        assert small_model_context._opt_enabled("opt1_prompt_state_machine") is True

    @pytest.mark.unit
    def test_large_model_always_returns_false(self, large_model_context):
        assert large_model_context._opt_enabled("opt1_prompt_state_machine") is False

    @pytest.mark.unit
    def test_flag_disabled_returns_false(self, small_model_context):
        small_model_context.config["small_model_optimizations"]["opt1_prompt_state_machine"] = False
        assert small_model_context._opt_enabled("opt1_prompt_state_machine") is False

    @pytest.mark.unit
    def test_missing_key_defaults_true_for_small_model(self, small_model_context):
        # If a flag is not present in the config it defaults to enabled for small models
        small_model_context.config["small_model_optimizations"] = {}
        assert small_model_context._opt_enabled("opt1_prompt_state_machine") is True

    @pytest.mark.unit
    def test_missing_section_defaults_true_for_small_model(self, small_model_context):
        small_model_context.config = {}
        assert small_model_context._opt_enabled("opt1_prompt_state_machine") is True

    @pytest.mark.unit
    def test_get_client_exception_treated_as_large_model(self):
        deps = _make_deps()
        ctx = PhaseContext(**deps)
        ctx.llm_manager.get_client.side_effect = RuntimeError("connection refused")
        assert ctx._opt_enabled("opt1_prompt_state_machine") is False


# ---------------------------------------------------------------------------
# Tests: build_micro_context_snapshot() (Opt 2)
# ---------------------------------------------------------------------------


class TestBuildMicroContextSnapshot:
    @pytest.mark.unit
    def test_returns_at_most_two_files(self, small_model_context):
        small_model_context.current_generated_files = {
            "utils.py": "def helper(): pass",
            "models.py": "class User: pass",
            "config.py": "DEBUG = True",
        }
        small_model_context.dependency_graph.get_context_for_file.return_value = [
            "utils.py", "models.py", "config.py"
        ]
        snapshot = small_model_context.build_micro_context_snapshot("app.py")
        assert len(snapshot) <= 2

    @pytest.mark.unit
    def test_enforces_token_budget(self, small_model_context):
        big_content = "x" * 10_000
        small_model_context.current_generated_files = {"utils.py": big_content}
        small_model_context.dependency_graph.get_context_for_file.return_value = ["utils.py"]
        snapshot = small_model_context.build_micro_context_snapshot("app.py", max_tokens=100)
        total_chars = sum(len(v) for v in snapshot.values())
        assert total_chars <= 100 * 4 + 50  # Allow small tolerance for the proportional trim

    @pytest.mark.unit
    def test_falls_back_when_graph_returns_nothing(self, small_model_context):
        small_model_context.dependency_graph.get_context_for_file.return_value = []
        small_model_context.rag_context_selector.select_relevant_files.return_value = {
            "utils.py": "def f(): pass"
        }
        snapshot = small_model_context.build_micro_context_snapshot("app.py")
        # Fallback path is select_related_files which calls rag_context_selector
        assert isinstance(snapshot, dict)

    @pytest.mark.unit
    def test_extracts_only_signatures_not_full_content(self, small_model_context):
        full_content = "def foo():\n    x = 1\n    return x\n\ndef bar():\n    return 2\n"
        small_model_context.current_generated_files = {"utils.py": full_content}
        small_model_context.dependency_graph.get_context_for_file.return_value = ["utils.py"]
        snapshot = small_model_context.build_micro_context_snapshot("app.py")
        value = snapshot.get("utils.py", "")
        # Signatures only: function bodies should not appear
        assert "x = 1" not in value
        assert "return x" not in value

    @pytest.mark.unit
    def test_graph_exception_falls_back_gracefully(self, small_model_context):
        small_model_context.dependency_graph.get_context_for_file.side_effect = RuntimeError("graph broken")
        small_model_context.rag_context_selector.select_relevant_files.return_value = {}
        # Should not raise
        snapshot = small_model_context.build_micro_context_snapshot("app.py")
        assert isinstance(snapshot, dict)


# ---------------------------------------------------------------------------
# Tests: _check_output_contract() (Opt 3)
# ---------------------------------------------------------------------------


class TestCheckOutputContract:
    @pytest.mark.unit
    def test_define_imports_accepts_pure_imports(self, phase):
        content = "import os\nfrom pathlib import Path\nimport json"
        assert phase._check_output_contract("utils.py", content, "define_imports") == ""

    @pytest.mark.unit
    def test_define_imports_rejects_function_def_python(self, phase):
        content = "import os\n\ndef my_func():\n    return 1"
        error = phase._check_output_contract("utils.py", content, "define_imports")
        assert error != ""
        assert "import" in error.lower()

    @pytest.mark.unit
    def test_define_imports_rejects_class_def_python(self, phase):
        content = "import os\n\nclass MyClass:\n    pass"
        error = phase._check_output_contract("utils.py", content, "define_imports")
        assert error != ""

    @pytest.mark.unit
    def test_define_imports_rejects_function_non_python(self, phase):
        content = "const x = require('fs');\nfunction myFunc() { return 1; }"
        error = phase._check_output_contract("utils.js", content, "define_imports")
        assert error != ""

    @pytest.mark.unit
    def test_implement_function_accepts_function_def(self, phase):
        content = "def my_function(x: int) -> int:\n    return x * 2"
        assert phase._check_output_contract("calc.py", content, "implement_function") == ""

    @pytest.mark.unit
    def test_implement_function_rejects_no_def(self, phase):
        content = "x = 1\ny = 2"
        error = phase._check_output_contract("calc.py", content, "implement_function")
        assert error != ""

    @pytest.mark.unit
    def test_write_tests_accepts_test_function(self, phase):
        content = "def test_something():\n    assert True"
        assert phase._check_output_contract("test_calc.py", content, "write_tests") == ""

    @pytest.mark.unit
    def test_write_tests_rejects_missing_test_prefix(self, phase):
        content = "def helper():\n    pass"
        error = phase._check_output_contract("test_calc.py", content, "write_tests")
        assert error != ""
        assert "test_" in error

    @pytest.mark.unit
    def test_unknown_task_type_always_passes(self, phase):
        content = "anything goes here"
        assert phase._check_output_contract("f.py", content, "create_file") == ""
        assert phase._check_output_contract("f.py", content, "write_config") == ""

    @pytest.mark.unit
    def test_empty_content_always_passes(self, phase):
        assert phase._check_output_contract("f.py", "", "define_imports") == ""
