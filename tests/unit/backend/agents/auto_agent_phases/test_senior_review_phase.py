"""Unit tests for SeniorReviewPhase."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.senior_review_phase import SeniorReviewPhase


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestGame",
        project_description="A chess game in HTML/JS/CSS",
        project_root=Path("/tmp/test_senior"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


_REVIEW_PASSED = {"status": "passed", "summary": "Looks great", "issues": []}

_REVIEW_FAILED = {
    "status": "failed",
    "summary": "Missing win logic",
    "issues": [
        {
            "severity": "critical",
            "file": "game.js",
            "description": "No win condition implemented",
            "recommendation": "Add checkWin() function",
        }
    ],
}


# ----------------------------------------------------------------
# Small model skip
# ----------------------------------------------------------------


@pytest.mark.unit
def test_skipped_for_small_model():
    ctx = _make_ctx(model_name="qwen3.5:4b")  # 4B = small
    SeniorReviewPhase().run(ctx)
    assert "senior_review" not in ctx.metrics


@pytest.mark.unit
def test_skipped_for_8b_model():
    ctx = _make_ctx(model_name="llama:8b")
    SeniorReviewPhase().run(ctx)
    assert "senior_review" not in ctx.metrics


# ----------------------------------------------------------------
# Passing review
# ----------------------------------------------------------------


@pytest.mark.unit
def test_records_metrics_on_pass():
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"game.js": "function init() {}"}

    with patch("backend.utils.domains.auto_generation.review.senior_reviewer.SeniorReviewer") as MockReviewer:
        MockReviewer.return_value.perform_review.return_value = _REVIEW_PASSED
        SeniorReviewPhase().run(ctx)

    assert ctx.metrics["senior_review"]["final_status"] == "passed"
    assert len(ctx.metrics["senior_review"]["cycles"]) == 1
    assert ctx.metrics["senior_review"]["cycles"][0]["status"] == "passed"


# ----------------------------------------------------------------
# Failing review with repair
# ----------------------------------------------------------------


@pytest.mark.unit
def test_fixes_critical_issue_then_passes():
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"game.js": "function init() {}"}

    patched_content = "function init() {}\nfunction checkWin() { return false; }"

    with (
        patch("backend.utils.domains.auto_generation.review.senior_reviewer.SeniorReviewer") as MockSR,
        patch("backend.utils.domains.auto_generation.utilities.code_patcher.CodePatcher") as MockCP,
    ):
        # First cycle fails, second passes
        MockSR.return_value.perform_review.side_effect = [_REVIEW_FAILED, _REVIEW_PASSED]
        MockCP.return_value.edit_existing_file.return_value = patched_content

        phase = SeniorReviewPhase()
        # Patch _write_file to avoid disk writes
        phase._write_file = lambda ctx_, rel, content: ctx_.generated_files.update({rel: content})
        phase.run(ctx)

    cycles = ctx.metrics["senior_review"]["cycles"]
    assert len(cycles) >= 1
    assert cycles[0]["issues_fixed"] >= 1


@pytest.mark.unit
def test_stops_after_max_cycles_on_persistent_failure():
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"game.js": "function init() {}"}

    with (
        patch("backend.utils.domains.auto_generation.review.senior_reviewer.SeniorReviewer") as MockSR,
        patch("backend.utils.domains.auto_generation.utilities.code_patcher.CodePatcher") as MockCP,
    ):
        # Always fails (2 cycles max)
        MockSR.return_value.perform_review.return_value = _REVIEW_FAILED
        MockCP.return_value.edit_existing_file.return_value = "// patched"

        phase = SeniorReviewPhase()
        phase._write_file = lambda ctx_, rel, content: ctx_.generated_files.update({rel: content})
        phase.run(ctx)

    # Should have run exactly 2 cycles
    assert len(ctx.metrics["senior_review"]["cycles"]) == 2
    assert ctx.metrics["senior_review"]["final_status"] == "failed"


# ----------------------------------------------------------------
# Robustness
# ----------------------------------------------------------------


@pytest.mark.unit
def test_continues_after_reviewer_raises():
    """Phase must not raise even if SeniorReviewer throws a runtime error."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"main.py": "print('hello')"}

    with patch("backend.utils.domains.auto_generation.review.senior_reviewer.SeniorReviewer") as MockReviewer:
        MockReviewer.return_value.perform_review.side_effect = RuntimeError("LLM timeout")
        SeniorReviewPhase().run(ctx)  # must not raise


@pytest.mark.unit
def test_continues_when_senior_reviewer_import_fails():
    """Phase must not raise if SeniorReviewer cannot be imported."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"main.py": "print('hello')"}

    with patch.dict("sys.modules", {"backend.utils.domains.auto_generation.review.senior_reviewer": None}):
        # ImportError will be raised inside _call_senior_reviewer
        SeniorReviewPhase().run(ctx)  # must not raise


@pytest.mark.unit
def test_skips_fix_for_missing_file():
    """If reviewer identifies a file that doesn't exist, fix is skipped gracefully."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.generated_files = {"game.js": "function init() {}"}

    review_with_unknown_file = {
        "status": "failed",
        "summary": "Missing handler",
        "issues": [
            {
                "severity": "critical",
                "file": "nonexistent_file.js",
                "description": "File not found",
                "recommendation": "Create it",
            }
        ],
    }

    with patch("backend.utils.domains.auto_generation.review.senior_reviewer.SeniorReviewer") as MockSR:
        MockSR.return_value.perform_review.return_value = review_with_unknown_file
        SeniorReviewPhase().run(ctx)  # must not raise

    assert ctx.metrics["senior_review"]["cycles"][0]["issues_fixed"] == 0


# ----------------------------------------------------------------
# _build_truncated_files helper
# ----------------------------------------------------------------


@pytest.mark.unit
def test_build_truncated_files_respects_budget():
    ctx = _make_ctx()
    # Create files that together exceed the budget
    ctx.generated_files = {f"file{i}.py": "x" * 5000 for i in range(10)}

    result = SeniorReviewPhase._build_truncated_files(ctx)

    total_chars = sum(len(v) for v in result.values())
    # Should not exceed budget + some overhead for truncation markers
    from backend.agents.auto_agent_phases.senior_review_phase import _CHAR_BUDGET

    assert total_chars <= _CHAR_BUDGET + 500  # small tolerance for truncation markers


@pytest.mark.unit
def test_build_truncated_files_keeps_small_files_intact():
    ctx = _make_ctx()
    ctx.generated_files = {
        "small.py": "print('hello')",
        "also_small.js": "console.log('hi')",
    }
    result = SeniorReviewPhase._build_truncated_files(ctx)
    assert result["small.py"] == "print('hello')"
    assert result["also_small.js"] == "console.log('hi')"
