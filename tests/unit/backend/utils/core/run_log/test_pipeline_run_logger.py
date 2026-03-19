"""Unit tests for PipelineRunLogger.

Tests that the logger writes the expected content to OLLASH_RUN_LOG.md
without needing a running pipeline.
"""

from __future__ import annotations

import concurrent.futures
import re
from pathlib import Path

import pytest

from backend.utils.core.run_log.pipeline_run_logger import PipelineRunLogger


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def logger_at_tmp(tmp_path: Path):
    """Create a PipelineRunLogger, yield (logger, log_path), then close."""
    logger = PipelineRunLogger(tmp_path, "TestProject", "A test project description")
    log_path = tmp_path / PipelineRunLogger.LOG_FILENAME
    yield logger, log_path
    logger.close()


def _read(log_path: Path) -> str:
    return log_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------


class TestInit:
    @pytest.mark.unit
    def test_creates_log_file_in_project_root(self, tmp_path: Path) -> None:
        logger = PipelineRunLogger(tmp_path, "MyApp", "desc")
        log_path = tmp_path / PipelineRunLogger.LOG_FILENAME
        assert log_path.exists()
        logger.close()

    @pytest.mark.unit
    def test_header_contains_project_name(self, logger_at_tmp) -> None:
        _, log_path = logger_at_tmp
        assert "TestProject" in _read(log_path)

    @pytest.mark.unit
    def test_header_contains_timestamp(self, logger_at_tmp) -> None:
        _, log_path = logger_at_tmp
        content = _read(log_path)
        # ISO timestamp pattern: YYYY-MM-DD HH:MM:SS
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content)

    @pytest.mark.unit
    def test_header_contains_description_preview(self, logger_at_tmp) -> None:
        _, log_path = logger_at_tmp
        assert "A test project description" in _read(log_path)

    @pytest.mark.unit
    def test_close_flushes_and_does_not_raise(self, tmp_path: Path) -> None:
        logger = PipelineRunLogger(tmp_path, "X", "y")
        logger.close()
        # second close must not raise
        logger.close()


# ---------------------------------------------------------------------------
# TestLogPipelineStart
# ---------------------------------------------------------------------------


class TestLogPipelineStart:
    @pytest.mark.unit
    def test_pipeline_config_table_written(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(
            phase_order=["ProjectScanPhase", "BlueprintPhase"],
            model_name="qwen3.5:4b",
            tier="small (<=8B)",
            complexity=5,
            num_refine_loops=3,
        )
        content = _read(log_path)
        assert "Pipeline Configuration" in content
        assert "qwen3.5:4b" in content
        assert "small (<=8B)" in content
        assert "ProjectScanPhase" in content
        assert "5/10" in content
        assert "3" in content

    @pytest.mark.unit
    def test_phase_execution_log_heading_written(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["PhaseA"], "model", "full", 3, 2)
        assert "Phase Execution Log" in _read(log_path)


# ---------------------------------------------------------------------------
# TestLogPhaseLifecycle
# ---------------------------------------------------------------------------


class TestLogPhaseLifecycle:
    @pytest.mark.unit
    def test_phase_start_writes_heading(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("1", "Project Scan")
        content = _read(log_path)
        assert "### Phase 1: Project Scan" in content

    @pytest.mark.unit
    def test_phase_end_success_writes_elapsed(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("2", "Blueprint")
        logger.log_phase_end("2", "Blueprint", 2.34, "success")
        content = _read(log_path)
        assert "2.34s" in content
        assert "success" in content

    @pytest.mark.unit
    def test_phase_end_error_writes_error_message(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("3", "Scaffold")
        logger.log_phase_end("3", "Scaffold", 0.0, "error", "JSON parse failed")
        content = _read(log_path)
        assert "error" in content
        assert "JSON parse failed" in content

    @pytest.mark.unit
    def test_phase_skipped_writes_skipped(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_skipped("6b", "Senior Review", "small model tier")
        content = _read(log_path)
        assert "Senior Review" in content
        assert "skipped" in content
        assert "small model tier" in content


# ---------------------------------------------------------------------------
# TestLogLlmCall
# ---------------------------------------------------------------------------


class TestLogLlmCall:
    @pytest.mark.unit
    def test_llm_call_writes_role_and_tokens(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("2", "Blueprint")
        logger.log_llm_call(
            phase_id="2",
            call_index=1,
            role="coder",
            system="You are an architect",
            user="Build a FastAPI app",
            response='{"files": []}',
            prompt_tokens=312,
            completion_tokens=891,
            elapsed_ms=2380.0,
        )
        content = _read(log_path)
        assert "coder" in content
        assert "312" in content
        assert "891" in content
        assert "2380" in content

    @pytest.mark.unit
    def test_llm_call_wraps_prompts_in_details_blocks(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("2", "Blueprint")
        logger.log_llm_call("2", 1, "coder", "sys prompt", "user prompt", "resp", 10, 20, 100.0)
        content = _read(log_path)
        assert "<details>" in content
        assert "<summary>System Prompt</summary>" in content
        assert "<summary>User Prompt</summary>" in content
        assert "sys prompt" in content
        assert "user prompt" in content

    @pytest.mark.unit
    def test_llm_call_wraps_response_in_details_block(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("2", "Blueprint")
        logger.log_llm_call("2", 1, "coder", "sys", "usr", "my response here", 5, 10, 50.0)
        content = _read(log_path)
        assert "<summary>Response</summary>" in content
        assert "my response here" in content

    @pytest.mark.unit
    def test_llm_call_increments_call_index(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4", "Code Fill")
        # Simulate two calls in the same phase
        logger.log_llm_call("4", logger._next_call_index("4"), "coder", "s", "u1", "r1", 5, 10, 50.0)
        logger.log_llm_call("4", logger._next_call_index("4"), "coder", "s", "u2", "r2", 5, 10, 50.0)
        content = _read(log_path)
        assert "LLM Call 1" in content
        assert "LLM Call 2" in content

    @pytest.mark.unit
    def test_no_think_flag_noted(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("2", "Blueprint")
        logger.log_llm_call("2", 1, "coder", "s", "u", "r", 5, 5, 100.0, no_think=True)
        content = _read(log_path)
        assert "thinking disabled" in content

    @pytest.mark.unit
    def test_triple_backtick_in_response_does_not_break_fencing(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("2", "Blueprint")
        response_with_backticks = "```python\nprint('hi')\n```"
        logger.log_llm_call("2", 1, "coder", "s", "u", response_with_backticks, 5, 5, 50.0)
        content = _read(log_path)
        # Content should be readable without broken fences
        assert "Response" in content
        # The escaped version should appear (~~~ instead of ```)
        assert "~~~" in content


# ---------------------------------------------------------------------------
# TestLogFileWritten
# ---------------------------------------------------------------------------


class TestLogFileWritten:
    @pytest.mark.unit
    def test_file_written_ok_appears_in_output(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4", "Code Fill")
        logger.log_file_written("4", "main.py", 1842, "ok")
        content = _read(log_path)
        assert "main.py" in content
        assert "1,842" in content
        assert "ok" in content

    @pytest.mark.unit
    def test_file_written_retry_ok_marked(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4", "Code Fill")
        logger.log_file_written("4", "auth.py", 900, "retry_ok", "SyntaxError line 12")
        content = _read(log_path)
        assert "auth.py" in content
        assert "retry_ok" in content
        assert "SyntaxError line 12" in content

    @pytest.mark.unit
    def test_file_written_retry_failed_marked(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4", "Code Fill")
        logger.log_file_written("4", "bad.py", 200, "retry_failed", "IndentationError")
        content = _read(log_path)
        assert "retry_failed" in content
        assert "⚠" in content

    @pytest.mark.unit
    def test_file_written_ok_has_check_mark(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4", "Code Fill")
        logger.log_file_written("4", "models.py", 500, "ok")
        content = _read(log_path)
        assert "✓" in content


# ---------------------------------------------------------------------------
# TestLogCrossFileErrors
# ---------------------------------------------------------------------------


class TestLogCrossFileErrors:
    @pytest.mark.unit
    def test_no_errors_writes_clean_summary(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4b", "Cross-File Validation")
        logger.log_cross_file_errors(0, 0, [])
        content = _read(log_path)
        assert "No contract errors" in content

    @pytest.mark.unit
    def test_error_table_has_correct_columns(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4b", "Cross-File Validation")
        errors = [
            {
                "file_a": "app.js",
                "file_b": "index.html",
                "error_type": "id_mismatch",
                "description": "JS refs #user-form not in HTML",
                "suggestion": "Add id=user-form to HTML",
            }
        ]
        logger.log_cross_file_errors(2, 1, errors)
        content = _read(log_path)
        assert "file_a" in content
        assert "file_b" in content
        assert "error_type" in content
        assert "app.js" in content
        assert "id_mismatch" in content
        assert "2 errors found" in content
        assert "1 auto-fixed" in content


# ---------------------------------------------------------------------------
# TestLogPatchRound
# ---------------------------------------------------------------------------


class TestLogPatchRound:
    @pytest.mark.unit
    def test_patch_round_start_writes_heading(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("5", "Patch")
        logger.log_patch_round_start(1, 3)
        assert "Patch Round 1/3" in _read(log_path)

    @pytest.mark.unit
    def test_patch_fix_with_diff_writes_diff_fence(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("5", "Patch")
        diff_lines = ["--- a/app.js\n", "+++ b/app.js\n", "- old line\n", "+ new line\n"]
        logger.log_patch_fix(1, "app.js", "JS ref missing", diff_lines, success=True)
        content = _read(log_path)
        assert "```diff" in content
        assert "- old line" in content
        assert "+ new line" in content

    @pytest.mark.unit
    def test_patch_fix_no_diff_skips_diff_fence(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("5", "Patch")
        logger.log_patch_fix(1, "app.js", "JS ref missing", None, success=False)
        content = _read(log_path)
        assert "app.js" in content
        assert "```diff" not in content

    @pytest.mark.unit
    def test_patch_round_end_writes_summary(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("5", "Patch")
        logger.log_patch_round_end(1, 2)
        content = _read(log_path)
        assert "2 fixes applied" in content

    @pytest.mark.unit
    def test_patch_round_end_singular_noun(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("5", "Patch")
        logger.log_patch_round_end(1, 1)
        assert "1 fix applied" in _read(log_path)


# ---------------------------------------------------------------------------
# TestLogSeniorReviewCycle
# ---------------------------------------------------------------------------


class TestLogSeniorReviewCycle:
    @pytest.mark.unit
    def test_review_cycle_passed_writes_passed(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("6b", "Senior Review")
        logger.log_senior_review_cycle(1, "passed", "All checks passed", 0, 0, [])
        content = _read(log_path)
        assert "Review Cycle 1" in content
        assert "passed" in content

    @pytest.mark.unit
    def test_review_cycle_failed_writes_issue_table(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("6b", "Senior Review")
        issues = [{"severity": "critical", "file": "main.py", "description": "Missing error handler"}]
        logger.log_senior_review_cycle(1, "failed", "Issues found", 1, 0, issues)
        content = _read(log_path)
        assert "failed" in content
        assert "critical" in content
        assert "main.py" in content
        assert "Missing error handler" in content


# ---------------------------------------------------------------------------
# TestLogTestIteration
# ---------------------------------------------------------------------------


class TestLogTestIteration:
    @pytest.mark.unit
    def test_test_iteration_passed_writes_passed(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("7", "Test Run")
        logger.log_test_iteration(1, "pytest", True, [], 0)
        content = _read(log_path)
        assert "Test Iteration 1" in content
        assert "passed" in content

    @pytest.mark.unit
    def test_test_iteration_failures_written(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_phase_start("7", "Test Run")
        failures = [{"file_path": "test_auth.py", "test_name": "test_login", "error": "AssertionError: 401"}]
        logger.log_test_iteration(1, "pytest", False, failures, 1)
        content = _read(log_path)
        assert "test_login" in content
        assert "AssertionError" in content
        assert "1 patch" in content or "patches_applied: 1" in content or "Patches applied:** 1" in content


# ---------------------------------------------------------------------------
# TestLogPipelineEnd
# ---------------------------------------------------------------------------


class TestLogPipelineEnd:
    @pytest.mark.unit
    def test_pipeline_end_writes_summary_section(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "model", "small (<=8B)", 3, 2)
        logger.log_pipeline_end(60.0, 9, 8312, [])
        content = _read(log_path)
        assert "Pipeline Summary" in content
        assert "60.0s" in content
        assert "8,312" in content

    @pytest.mark.unit
    def test_pipeline_end_writes_errors_when_present(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "model", "full (>8B)", 2, 3)
        logger.log_pipeline_end(60.0, 9, 8312, ["CodeFill: failed to generate x.py"])
        content = _read(log_path)
        assert "CodeFill: failed to generate x.py" in content

    @pytest.mark.unit
    def test_pipeline_end_triggers_auto_insights(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "model", "full", 2, 3)
        logger.log_pipeline_end(60.0, 5, 1000, [])
        assert "Auto-Insights" in _read(log_path)


# ---------------------------------------------------------------------------
# TestAutoInsights
# ---------------------------------------------------------------------------


class TestAutoInsights:
    @pytest.mark.unit
    def test_insights_token_efficiency_section(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1", "P2"], "qwen3.5:4b", "small (<=8B)", 4, 2)
        logger.log_phase_start("4", "Code Fill")
        logger.log_llm_call("4", 1, "coder", "s", "u", "r", 200, 800, 3000.0)
        logger.log_phase_end("4", "Code Fill", 5.0, "success")
        logger.log_pipeline_end(10.0, 3, 1000, [])
        content = _read(log_path)
        assert "Token Efficiency" in content

    @pytest.mark.unit
    def test_insights_flags_complexity_warning_for_small_model(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "qwen3.5:4b", "small (<=8B)", 7, 2)
        logger.log_pipeline_end(30.0, 5, 500, [])
        content = _read(log_path)
        assert "7/10" in content
        # Should contain a recommendation for high complexity on small model
        assert ">8B" in content or "larger model" in content.lower()

    @pytest.mark.unit
    def test_insights_no_warning_for_low_complexity_small_model(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "qwen3.5:4b", "small (<=8B)", 2, 2)
        logger.log_pipeline_end(10.0, 3, 200, [])
        content = _read(log_path)
        assert "appropriate for this complexity" in content

    @pytest.mark.unit
    def test_insights_phase_timing_table(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1", "P2"], "model", "full (>8B)", 3, 3)
        logger.log_phase_start("1", "Project Scan")
        logger.log_phase_end("1", "Project Scan", 0.05, "success")
        logger.log_phase_start("2", "Blueprint")
        logger.log_phase_end("2", "Blueprint", 2.3, "success")
        logger.log_pipeline_end(3.0, 5, 1000, [])
        content = _read(log_path)
        assert "Phase Timing" in content
        assert "0.05s" in content
        assert "2.30s" in content

    @pytest.mark.unit
    def test_insights_cross_file_clean_pass(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "model", "full", 2, 3)
        logger.log_cross_file_errors(0, 0, [])
        logger.log_pipeline_end(10.0, 5, 500, [])
        content = _read(log_path)
        assert "No contract errors" in content

    @pytest.mark.unit
    def test_insights_syntax_retry_rate(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "model", "full", 2, 3)
        logger.log_phase_start("4", "Code Fill")
        logger.log_file_written("4", "a.py", 100, "retry_ok")
        logger.log_file_written("4", "b.py", 100, "retry_failed")
        logger.log_pipeline_end(10.0, 5, 500, [])
        content = _read(log_path)
        assert "retry" in content.lower()

    @pytest.mark.unit
    def test_insights_test_skipped_for_small_model(self, logger_at_tmp) -> None:
        logger, log_path = logger_at_tmp
        logger.log_pipeline_start(["P1"], "model", "small (<=8B)", 2, 2)
        logger.log_pipeline_end(10.0, 3, 200, [])
        content = _read(log_path)
        assert "small model tier" in content


# ---------------------------------------------------------------------------
# TestThreadSafety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    @pytest.mark.unit
    def test_concurrent_writes_do_not_interleave(self, logger_at_tmp) -> None:
        """10 threads each write 1 LLM call; assert 10 blocks, no corruption."""
        logger, log_path = logger_at_tmp
        logger.log_phase_start("4", "Code Fill")

        def write_one(_: int) -> None:
            idx = logger._next_call_index("4")
            logger.log_llm_call(
                phase_id="4",
                call_index=idx,
                role="coder",
                system="system prompt",
                user=f"user prompt {idx}",
                response=f"response {idx}",
                prompt_tokens=10,
                completion_tokens=20,
                elapsed_ms=100.0,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(write_one, range(10)))

        content = _read(log_path)
        # All 10 blocks should be present
        call_blocks = re.findall(r"#### LLM Call \d+", content)
        assert len(call_blocks) == 10

    @pytest.mark.unit
    def test_counter_increments_atomically(self, logger_at_tmp) -> None:
        """Concurrent _next_call_index calls must produce unique indices."""
        logger, _ = logger_at_tmp

        indices: list[int] = []
        lock = __import__("threading").Lock()

        def get_index(_: int) -> None:
            idx = logger._next_call_index("test_phase")
            with lock:
                indices.append(idx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            list(executor.map(get_index, range(20)))

        assert len(set(indices)) == 20  # all unique
        assert set(indices) == set(range(1, 21))  # 1 through 20
