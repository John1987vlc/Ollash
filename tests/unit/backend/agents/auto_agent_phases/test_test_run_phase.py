"""Unit tests for TestRunPhase — I9 improvements."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.test_run_phase import (
    TestRunPhase,
    _MAX_ITERATIONS_LARGE,
    _MAX_ITERATIONS_SMALL,
)


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestProject",
        project_description="A Python web app",
        project_root=Path("/tmp/test_testrun"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


# ----------------------------------------------------------------
# I9 — Iteration counts
# ----------------------------------------------------------------


@pytest.mark.unit
def test_i9_large_model_max_iterations_constant():
    """I9: Large model iteration constant is 5."""
    assert _MAX_ITERATIONS_LARGE == 5


@pytest.mark.unit
def test_i9_small_model_max_iterations_constant():
    """I9: Small model iteration constant is 3."""
    assert _MAX_ITERATIONS_SMALL == 3


@pytest.mark.unit
def test_i9_large_model_runs_up_to_5_iterations():
    """I9: Large model (>8B) performs up to 5 test-run iterations on persistent failure."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"test_app.py": "def test_foo(): assert False"}

    iteration_count = 0
    _fake_failure = [{"file_path": "test_app.py", "test_name": "test_foo", "error": "AssertionError"}]

    def fake_run_tests(ctx_, runner):
        nonlocal iteration_count
        iteration_count += 1
        return {"passed": False, "failures": _fake_failure}

    phase = TestRunPhase()
    phase._run_tests = fake_run_tests
    phase._patch_failure = lambda ctx_, failure: False  # no-op patching
    phase.run(ctx)

    assert iteration_count == _MAX_ITERATIONS_LARGE


@pytest.mark.unit
def test_i9_small_model_runs_up_to_3_iterations():
    """I9: Small model (≤8B) performs up to 3 test-run iterations on persistent failure."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.generated_files = {"test_app.py": "def test_foo(): assert False"}

    iteration_count = 0
    _fake_failure = [{"file_path": "test_app.py", "test_name": "test_foo", "error": "AssertionError"}]

    def fake_run_tests(ctx_, runner):
        nonlocal iteration_count
        iteration_count += 1
        return {"passed": False, "failures": _fake_failure}

    phase = TestRunPhase()
    phase._run_tests = fake_run_tests
    phase._patch_failure = lambda ctx_, failure: False  # no-op patching
    phase.run(ctx)

    assert iteration_count == _MAX_ITERATIONS_SMALL


# ----------------------------------------------------------------
# I9 — Post-success ruff check
# ----------------------------------------------------------------


@pytest.mark.unit
def test_i9_post_success_ruff_check_called_after_pass():
    """I9: _post_success_ruff_check is invoked when tests pass."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"test_app.py": "def test_foo(): pass", "app.py": "x = 1"}

    phase = TestRunPhase()
    phase._run_tests = lambda ctx_, runner: {"passed": True, "failures": []}
    ruff_called = []
    phase._post_success_ruff_check = lambda ctx_: ruff_called.append(True)
    phase.run(ctx)

    assert ruff_called


@pytest.mark.unit
def test_i9_post_success_ruff_records_issue_count():
    """I9: _post_success_ruff_check stores count in ctx.metrics."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"app.py": "x=1"}

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stdout = '[{"code":"E501","filename":"app.py","row":1,"col":1,"message":"line too long"}]'

    with patch("subprocess.run", return_value=fake_result):
        TestRunPhase()._post_success_ruff_check(ctx)

    assert ctx.metrics.get("post_test_ruff_issues") == 1


@pytest.mark.unit
def test_i9_ruff_check_skipped_for_non_python_project():
    """I9: _post_success_ruff_check skips when no .py files exist."""
    ctx = _make_ctx()
    ctx.generated_files = {"index.html": "<html/>", "app.js": "const x = 1;"}

    with patch("subprocess.run") as mock_sub:
        TestRunPhase()._post_success_ruff_check(ctx)

    mock_sub.assert_not_called()
