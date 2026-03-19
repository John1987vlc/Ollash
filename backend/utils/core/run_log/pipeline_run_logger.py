"""Append-only pipeline run logger for AutoAgent.

Writes OLLASH_RUN_LOG.md into the generated project directory as the pipeline runs.
The file is progressively flushed after every write so a mid-run crash leaves a
readable partial log.

Thread-safe: a single threading.Lock guards all _append() calls.
CodeFillPhase uses a ThreadPoolExecutor, so concurrent log_llm_call() calls are
expected and must not interleave partial writes.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class PipelineRunLogger:
    """Append-only run log for one AutoAgent pipeline execution.

    Lifecycle:
        logger = PipelineRunLogger(project_root, project_name, description)
        logger.log_pipeline_start(...)
        # pipeline runs; phases call log_phase_start/end, log_llm_call, etc.
        logger.log_pipeline_end(...)
        logger.close()
    """

    LOG_FILENAME = "OLLASH_RUN_LOG.md"

    def __init__(self, project_root: Path, project_name: str, project_description: str) -> None:
        self._lock = threading.Lock()
        self._run_start_wall = datetime.now()

        project_root = Path(project_root)
        project_root.mkdir(parents=True, exist_ok=True)
        self._log_path = project_root / self.LOG_FILENAME
        self._fh = open(self._log_path, "w", encoding="utf-8")  # noqa: SIM115

        # Accumulated stats (all protected by _lock where mutated concurrently)
        self._phase_llm_counters: Dict[str, int] = {}  # phase_id → call counter
        self._total_llm_calls: int = 0
        self._total_llm_ms: float = 0.0
        self._syntax_retry_ok: int = 0
        self._syntax_retry_failed: int = 0
        self._patch_rounds_logged: int = 0
        self._patch_fixes_total: int = 0
        self._cross_val_errors_found: int = 0
        self._cross_val_errors_auto_fixed: int = 0
        self._cross_val_errors_remaining: int = 0
        self._test_iterations: int = 0
        self._test_final_passed: Optional[bool] = None
        self._test_first_iteration_failed: bool = False
        self._review_final_status: Optional[str] = None
        self._file_written_count: int = 0
        self._phase_timings: Dict[str, float] = {}
        self._phase_statuses: Dict[str, str] = {}

        # Config snapshot (set by log_pipeline_start)
        self._model_name: str = "unknown"
        self._tier: str = "unknown"
        self._complexity: int = 0
        self._is_small: bool = False
        self._phase_order: List[str] = []

        # Write header
        ts = self._fmt_timestamp()
        desc_preview = (project_description[:200] + "...") if len(project_description) > 200 else project_description
        self._append(
            f"# OLLASH_RUN_LOG — {project_name}\n\n**Run started:** {ts}  \n**Description:** {desc_preview}\n\n---\n\n"
        )

    # ------------------------------------------------------------------
    # Pipeline-level events
    # ------------------------------------------------------------------

    def log_pipeline_start(
        self,
        phase_order: List[str],
        model_name: str,
        tier: str,
        complexity: int,
        num_refine_loops: int,
    ) -> None:
        """Write ## Pipeline Configuration section."""
        self._model_name = model_name
        self._tier = tier
        self._complexity = complexity
        self._is_small = "small" in tier.lower()
        self._phase_order = phase_order

        phases_str = ", ".join(phase_order)
        self._append(
            "## Pipeline Configuration\n\n"
            "| Key | Value |\n"
            "|-----|-------|\n"
            f"| Model | `{model_name}` |\n"
            f"| Tier | {tier} |\n"
            f"| Phases | {phases_str} |\n"
            f"| Description complexity | {complexity}/10 |\n"
            f"| Refinement loops | {num_refine_loops} |\n"
            "\n---\n\n"
            "## Phase Execution Log\n\n"
        )

    def log_pipeline_end(
        self,
        elapsed_seconds: float,
        files_generated: int,
        total_tokens: int,
        errors: List[str],
    ) -> None:
        """Write ## Pipeline Summary and ## Auto-Insights sections."""
        errors_md = ""
        if errors:
            errors_md = "\n**Errors:**\n" + "\n".join(f"- {e}" for e in errors) + "\n"

        self._append(
            "---\n\n"
            "## Pipeline Summary\n\n"
            "| Key | Value |\n"
            "|-----|-------|\n"
            f"| Total elapsed | {elapsed_seconds:.1f}s |\n"
            f"| Files generated | {files_generated} |\n"
            f"| Total tokens | {total_tokens:,} |\n"
            f"| Non-fatal errors | {len(errors)} |\n"
            f"{errors_md}\n"
        )

        insights = self._compute_insights(elapsed_seconds, files_generated, total_tokens)
        self._append(insights)

    # ------------------------------------------------------------------
    # Phase-level events
    # ------------------------------------------------------------------

    def log_phase_start(self, phase_id: str, phase_label: str) -> None:
        """Write ### Phase N: <label> heading."""
        ts = self._fmt_timestamp()
        with self._lock:
            self._phase_llm_counters[phase_id] = 0
        self._append(f"### Phase {phase_id}: {phase_label}\n\n**Started:** {ts}\n\n")

    def log_phase_end(
        self,
        phase_id: str,
        phase_label: str,
        elapsed: float,
        status: str,
        error_msg: str = "",
    ) -> None:
        """Write the phase result line."""
        with self._lock:
            self._phase_timings[phase_id] = elapsed
            self._phase_statuses[phase_id] = status

        icon = "✓" if status == "success" else "✗"
        elapsed_str = f"{elapsed:.2f}s" if elapsed else "—"
        llm_calls = self._phase_llm_counters.get(phase_id, 0)
        error_str = f"  \n**Error:** {error_msg}" if error_msg else ""
        self._append(
            f"**Status:** {icon} {status} | **Elapsed:** {elapsed_str} | **LLM calls:** {llm_calls}"
            f"{error_str}\n\n---\n\n"
        )

    def log_phase_skipped(self, phase_id: str, phase_label: str, reason: str) -> None:
        """Write a skipped-phase entry."""
        self._append(f"### Phase {phase_id}: {phase_label}\n\n**Status:** ⏭ skipped — {reason}\n\n---\n\n")

    # ------------------------------------------------------------------
    # LLM call events
    # ------------------------------------------------------------------

    def _next_call_index(self, phase_id: str) -> int:
        """Thread-safe increment of per-phase LLM call counter."""
        with self._lock:
            idx = self._phase_llm_counters.get(phase_id, 0) + 1
            self._phase_llm_counters[phase_id] = idx
            self._total_llm_calls += 1
            return idx

    def log_llm_call(
        self,
        phase_id: str,
        call_index: int,
        role: str,
        system: str,
        user: str,
        response: str,
        prompt_tokens: int,
        completion_tokens: int,
        elapsed_ms: float,
        no_think: bool = False,
    ) -> None:
        """Write #### LLM Call N block with collapsible prompt/response sections."""
        with self._lock:
            self._total_llm_ms += elapsed_ms

        no_think_str = "yes" if no_think else "no"
        think_note = " *(thinking disabled)*" if no_think else ""

        block = (
            f"#### LLM Call {call_index}{think_note}\n\n"
            "| Attribute | Value |\n"
            "|-----------|-------|\n"
            f"| Role | `{role}` |\n"
            f"| Tokens | {prompt_tokens:,} prompt / {completion_tokens:,} completion |\n"
            f"| Elapsed | {elapsed_ms:.0f}ms |\n"
            f"| no_think | {no_think_str} |\n"
            "\n"
        )
        block += self._details_block("System Prompt", system)
        block += self._details_block("User Prompt", user)
        block += self._details_block("Response", response)
        block += "\n"
        self._append(block)

    # ------------------------------------------------------------------
    # File generation events
    # ------------------------------------------------------------------

    def log_file_written(
        self,
        phase_id: str,
        rel_path: str,
        char_count: int,
        validation_status: str = "ok",
        validation_detail: str = "",
    ) -> None:
        """Write a file-written bullet.

        validation_status: "ok" | "retry_ok" | "retry_failed" | "syntax_error"
        """
        with self._lock:
            self._file_written_count += 1
            if validation_status == "retry_ok":
                self._syntax_retry_ok += 1
            elif validation_status in ("retry_failed", "syntax_error"):
                self._syntax_retry_failed += 1

        icon = "✓" if validation_status in ("ok", "retry_ok") else "⚠"
        detail_str = f" ({validation_detail})" if validation_detail else ""
        self._append(
            f"- {icon} `{rel_path}` — {char_count:,} chars | validation: **{validation_status}**{detail_str}\n"
        )

    # ------------------------------------------------------------------
    # Cross-file validation events
    # ------------------------------------------------------------------

    def log_cross_file_errors(
        self,
        errors_found: int,
        errors_auto_fixed: int,
        remaining_errors: List[Dict[str, Any]],
    ) -> None:
        """Write the cross-file validation results."""
        with self._lock:
            self._cross_val_errors_found = errors_found
            self._cross_val_errors_auto_fixed = errors_auto_fixed
            self._cross_val_errors_remaining = len(remaining_errors)

        if errors_found == 0:
            self._append("**Cross-File Validation:** ✓ No contract errors found.\n\n")
            return

        self._append(
            f"**Cross-File Validation:** {errors_found} errors found, "
            f"{errors_auto_fixed} auto-fixed, "
            f"{len(remaining_errors)} passed to PatchPhase\n\n"
        )
        if remaining_errors:
            self._append(
                "| file_a | file_b | error_type | description | suggestion |\n"
                "|--------|--------|------------|-------------|------------|\n"
            )
            for err in remaining_errors:
                fa = err.get("file_a", "—")
                fb = err.get("file_b", "—")
                et = err.get("error_type", "—")
                desc = err.get("description", "—")[:80]
                sug = err.get("suggestion", "—")[:80]
                self._append(f"| `{fa}` | `{fb}` | {et} | {desc} | {sug} |\n")
            self._append("\n")

    # ------------------------------------------------------------------
    # Patch phase events
    # ------------------------------------------------------------------

    def log_patch_round_start(self, round_num: int, total_rounds: int) -> None:
        """Write Patch Round N/M heading."""
        self._append(f"#### Patch Round {round_num}/{total_rounds}\n\n")

    def log_patch_fix(
        self,
        round_num: int,
        file_path: str,
        issue_description: str,
        diff_lines: Optional[List[str]],
        success: bool,
    ) -> None:
        """Write a single patch fix entry with optional diff."""
        icon = "✓" if success else "✗"
        self._append(f"**{icon} Fix: `{file_path}`**  \n{issue_description}\n\n")
        if diff_lines:
            diff_content = "".join(diff_lines)
            self._append(f"```diff\n{diff_content}```\n\n")

    def log_patch_round_end(self, round_num: int, fixes_applied: int) -> None:
        """Write round summary."""
        with self._lock:
            self._patch_rounds_logged += 1
            self._patch_fixes_total += fixes_applied

        noun = "fix" if fixes_applied == 1 else "fixes"
        self._append(f"*Round {round_num} summary: {fixes_applied} {noun} applied*\n\n")

    # ------------------------------------------------------------------
    # Senior review events
    # ------------------------------------------------------------------

    def log_senior_review_cycle(
        self,
        cycle_num: int,
        status: str,
        summary: str,
        issues_found: int,
        issues_fixed: int,
        issues: List[Dict[str, Any]],
    ) -> None:
        """Write Senior Review Cycle N block."""
        with self._lock:
            self._review_final_status = status

        icon = "✓" if status == "passed" else "✗"
        self._append(
            f"#### Review Cycle {cycle_num}\n\n"
            f"**Status:** {icon} {status} | **Issues found:** {issues_found} | **Fixed:** {issues_fixed}  \n"
            f"**Summary:** {summary}\n\n"
        )
        if issues:
            self._append("| Severity | File | Description |\n|----------|------|-------------|\n")
            for issue in issues:
                sev = issue.get("severity", "?")
                f = issue.get("file", "?")
                desc = issue.get("description", "?")[:100]
                self._append(f"| {sev} | `{f}` | {desc} |\n")
            self._append("\n")

    # ------------------------------------------------------------------
    # Test run events
    # ------------------------------------------------------------------

    def log_test_iteration(
        self,
        iteration: int,
        runner: str,
        passed: bool,
        failures: List[Dict[str, str]],
        patches_applied: int,
    ) -> None:
        """Write Test Iteration N block."""
        with self._lock:
            self._test_iterations = iteration
            self._test_final_passed = passed
            if iteration == 1 and not passed:
                self._test_first_iteration_failed = True

        icon = "✓" if passed else "✗"
        self._append(
            f"#### Test Iteration {iteration} ({runner})\n\n"
            f"**Status:** {icon} {'passed' if passed else 'failed'}"
            f" | **Failures:** {len(failures)} | **Patches applied:** {patches_applied}\n\n"
        )
        if failures:
            self._append("| File | Test | Error |\n|------|------|-------|\n")
            for fail in failures[:10]:
                fp = fail.get("file_path", "?")
                tn = fail.get("test_name", "?")
                err = fail.get("error", "?")[:80]
                self._append(f"| `{fp}` | `{tn}` | {err} |\n")
            self._append("\n")

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Flush and close the file handle."""
        with self._lock:
            try:
                self._fh.flush()
                self._fh.close()
            except (OSError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, text: str) -> None:
        """Thread-safe append to log file, flush immediately."""
        with self._lock:
            try:
                self._fh.write(text)
                self._fh.flush()
            except (OSError, ValueError):
                pass  # File closed or disk error — don't crash the pipeline

    def _fmt_timestamp(self) -> str:
        """Return ISO-8601 local timestamp, seconds precision."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _details_block(summary: str, content: str) -> str:
        """Return a collapsed <details> block with fenced content."""
        # Escape triple-backtick sequences inside content to avoid breaking the fence
        safe_content = content.replace("```", "~~~")
        return f"<details>\n<summary>{summary}</summary>\n\n```\n{safe_content}\n```\n\n</details>\n\n"

    def _compute_insights(
        self,
        elapsed_seconds: float,
        files_generated: int,
        total_tokens: int,
    ) -> str:
        """Generate the ## Auto-Insights section from accumulated run data."""
        lines: List[str] = ["---\n", "\n## Auto-Insights\n\n"]

        # ------------------------------------------------------------------
        # A — Token Efficiency
        # ------------------------------------------------------------------
        lines.append("### Token Efficiency\n\n")

        if total_tokens > 0 and files_generated > 0:
            tpf = total_tokens / files_generated
            lines.append(f"- Average tokens per generated file: **{tpf:.0f}**\n")

        if total_tokens > 0 and self._total_llm_calls > 0:
            avg_per_call = total_tokens / self._total_llm_calls
            lines.append(f"- Total LLM calls: **{self._total_llm_calls}** | Avg tokens/call: **{avg_per_call:.0f}**\n")

        if self._phase_timings:
            # Find highest token phase from phase timings as a proxy
            slowest_phase = max(self._phase_timings, key=self._phase_timings.get)  # type: ignore[arg-type]
            slowest_elapsed = self._phase_timings[slowest_phase]
            lines.append(f"- Slowest phase by time: **Phase {slowest_phase}** ({slowest_elapsed:.1f}s)\n")

        lines.append("\n")

        # ------------------------------------------------------------------
        # B — Phase Timing
        # ------------------------------------------------------------------
        lines.append("### Phase Timing\n\n")

        if self._phase_timings:
            lines.append("| Phase | Status | Elapsed |\n")
            lines.append("|-------|--------|--------|\n")
            for pid, elapsed in sorted(self._phase_timings.items()):
                status = self._phase_statuses.get(pid, "?")
                icon = "✓" if status == "success" else ("✗" if status == "error" else "⏭")
                lines.append(f"| {pid} | {icon} {status} | {elapsed:.2f}s |\n")
            lines.append("\n")

        if self._total_llm_ms > 0:
            llm_wait_s = self._total_llm_ms / 1000.0
            non_llm_s = max(0.0, elapsed_seconds - llm_wait_s)
            avg_latency = self._total_llm_ms / max(1, self._total_llm_calls)
            lines.append(
                f"- Total LLM wait: **{llm_wait_s:.1f}s** | Non-LLM work: **{non_llm_s:.1f}s**\n"
                f"- Avg LLM call latency: **{avg_latency:.0f}ms** ({self._total_llm_calls} calls)\n"
            )
        lines.append("\n")

        # ------------------------------------------------------------------
        # C — Quality Signals
        # ------------------------------------------------------------------
        lines.append("### Quality Signals\n\n")

        # Cross-file validation
        if self._cross_val_errors_found == 0:
            lines.append("- Cross-file validation: ✓ No contract errors detected\n")
        else:
            lines.append(
                f"- Cross-file errors: **{self._cross_val_errors_found}** found, "
                f"**{self._cross_val_errors_auto_fixed}** auto-fixed, "
                f"**{self._cross_val_errors_remaining}** passed to PatchPhase\n"
            )

        # Patch rounds
        if self._patch_rounds_logged == 0:
            lines.append("- Patch: ✓ No improvement rounds needed (or PatchPhase skipped)\n")
        else:
            lines.append(
                f"- Patch: **{self._patch_rounds_logged}** round(s) | "
                f"**{self._patch_fixes_total}** total fix(es) applied\n"
            )

        # Syntax retries
        total_retries = self._syntax_retry_ok + self._syntax_retry_failed
        if total_retries == 0:
            lines.append("- Syntax retries: ✓ All files generated cleanly on first attempt\n")
        else:
            retry_success_rate = (self._syntax_retry_ok / total_retries * 100) if total_retries else 0
            lines.append(
                f"- Syntax retries: **{total_retries}** file(s) needed retry "
                f"(success rate: {retry_success_rate:.0f}%)\n"
            )

        # Senior review
        if self._review_final_status is not None:
            icon = "✓" if self._review_final_status == "passed" else "⚠"
            lines.append(f"- Senior review: {icon} final status **{self._review_final_status}**\n")
        else:
            lines.append("- Senior review: ⏭ skipped (small model tier or not in phase order)\n")

        # Tests
        if self._test_final_passed is None:
            lines.append("- Tests: ⏭ skipped (small model tier or no test files found)\n")
        elif self._test_final_passed:
            if self._test_first_iteration_failed:
                lines.append(
                    f"- Tests: ✓ passed after **{self._test_iterations}** iteration(s) (failed on first run)\n"
                )
            else:
                lines.append("- Tests: ✓ passed on first run\n")
        else:
            lines.append(
                f"- Tests: ✗ FAILED after **{self._test_iterations}** iteration(s) — check generated test files\n"
            )

        lines.append("\n")

        # ------------------------------------------------------------------
        # D — Complexity Assessment
        # ------------------------------------------------------------------
        lines.append("### Complexity Assessment\n\n")

        complexity_label = (
            "simple (0-3)" if self._complexity <= 3 else "moderate (4-6)" if self._complexity <= 6 else "high (7-10)"
        )
        lines.append(
            f"- Description complexity score: **{self._complexity}/10** — {complexity_label}\n"
            f"- Model tier: **{self._tier}**\n"
        )

        if self._is_small and self._complexity >= 5:
            lines.append(
                "- ⚠ **Recommendation:** This project scored "
                f"{self._complexity}/10 complexity on a small (≤8B) model. "
                "For better coverage (SeniorReview + TestRun phases), consider using a >8B model.\n"
            )
        elif not self._is_small and self._complexity <= 2:
            lines.append("- ℹ Simple project on a large model — a smaller/faster model may be sufficient next time.\n")
        else:
            lines.append("- Model tier appears appropriate for this complexity level.\n")

        lines.append("\n")

        # ------------------------------------------------------------------
        # E — File Distribution
        # ------------------------------------------------------------------
        lines.append("### File Distribution\n\n")
        lines.append(
            f"- Total files written during pipeline: **{self._file_written_count}**\n"
            f"- Files in final generated project: **{files_generated}**\n\n"
        )

        return "".join(lines)
