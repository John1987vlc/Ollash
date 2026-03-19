"""Phase 7: TestRunPhase — run tests and patch failures.

Runs the appropriate test command for the project's language: pytest (Python),
jest/vitest (JS/TS), go test (Go), cargo test (Rust), mvn test (Java).
For each failing test, locates the relevant source file and patches it.
Max 3 iterations.

Skipped automatically for small models (<=8B) — see AutoAgent.SMALL_PHASE_ORDER.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_MAX_ITERATIONS = 3
_PYTEST_TIMEOUT = 120
_TEST_TIMEOUT = 120


class TestRunPhase(BasePhase):
    phase_id = "7"
    phase_label = "Test Run"

    def run(self, ctx: PhaseContext) -> None:
        test_files = [p for p in ctx.generated_files if "test" in Path(p).name.lower()]
        if not test_files:
            ctx.logger.info("[TestRun] No test files found, skipping")
            ctx.metrics["tests_passed"] = None  # N/A
            return

        ctx.logger.info(f"[TestRun] Found {len(test_files)} test file(s)")

        # T1 — pick the right test runner for the project language
        runner = self._select_test_runner(ctx)
        ctx.logger.info(f"[TestRun] Using runner: {runner}")

        for iteration in range(_MAX_ITERATIONS):
            result = self._run_tests(ctx, runner)
            if result is None:
                ctx.logger.info(f"[TestRun] {runner} not available, skipping")
                return

            if result["passed"]:
                ctx.logger.info(f"[TestRun] All tests passed on iteration {iteration + 1}")
                ctx.metrics["tests_passed"] = True
                if ctx.run_logger:
                    ctx.run_logger.log_test_iteration(
                        iteration=iteration + 1,
                        runner=runner,
                        passed=True,
                        failures=[],
                        patches_applied=0,
                    )
                return

            failures = result.get("failures", [])
            ctx.logger.warning(f"[TestRun] Tests failed (iteration {iteration + 1}), {len(failures)} failure(s)")

            if not failures:
                break

            patched = 0
            for failure in failures[:3]:  # max 3 fixes per iteration
                if self._patch_failure(ctx, failure):
                    patched += 1
            ctx.logger.info(f"[TestRun] Patched {patched} file(s)")

            if ctx.run_logger:
                ctx.run_logger.log_test_iteration(
                    iteration=iteration + 1,
                    runner=runner,
                    passed=False,
                    failures=failures,
                    patches_applied=patched,
                )

        ctx.metrics["tests_passed"] = False

    @staticmethod
    def _select_test_runner(ctx: PhaseContext) -> str:
        """Pick the appropriate test runner based on project language."""
        stack = ctx.tech_stack
        ptype = ctx.project_type
        if ptype == "go_service" or any(t in stack for t in ("go", "golang")):
            return "go_test"
        if ptype == "rust_project" or "rust" in stack:
            return "cargo_test"
        if ptype in ("java_app", "kotlin_app") or any(t in stack for t in ("java", "kotlin", "spring")):
            return "mvn_test"
        if any(p.endswith((".ts", ".tsx")) for p in ctx.generated_files):
            return "jest_ts"
        if any(p.endswith(".js") for p in ctx.generated_files) and "python" not in stack:
            return "jest"
        return "pytest"  # default

    # ----------------------------------------------------------------

    def _run_tests(self, ctx: PhaseContext, runner: str) -> Optional[Dict]:
        """Dispatch to the appropriate test runner. Returns None if tool unavailable."""
        if runner == "go_test":
            return self._run_go_test(ctx)
        if runner == "cargo_test":
            return self._run_cargo_test(ctx)
        if runner == "mvn_test":
            return self._run_mvn_test(ctx)
        if runner in ("jest", "jest_ts"):
            return self._run_jest(ctx)
        return self._run_pytest(ctx)

    def _run_pytest(self, ctx: PhaseContext) -> Optional[Dict]:
        """Run pytest. Returns dict with passed/failures, or None if unavailable."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"],
                cwd=str(ctx.project_root),
                capture_output=True,
                text=True,
                timeout=_PYTEST_TIMEOUT,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return {"passed": True, "failures": []}

            failures = self._parse_failures(output)
            return {"passed": False, "failures": failures}
        except FileNotFoundError:
            return None  # pytest not installed
        except subprocess.TimeoutExpired:
            ctx.logger.warning("[TestRun] pytest timed out")
            return {"passed": False, "failures": []}

    def _run_go_test(self, ctx: PhaseContext) -> Optional[Dict]:
        """Run `go test ./...`."""
        try:
            result = subprocess.run(
                ["go", "test", "./...", "-v"],
                cwd=str(ctx.project_root),
                capture_output=True,
                text=True,
                timeout=_TEST_TIMEOUT,
            )
            if result.returncode == 0:
                return {"passed": True, "failures": []}
            # Parse go test failures: "--- FAIL: TestName (0.00s)"
            failures = []
            for line in (result.stdout + result.stderr).splitlines():
                m = re.match(r"--- FAIL:\s+(\S+)\s+\(", line)
                if m:
                    failures.append({"file_path": ".", "test_name": m.group(1), "error": line.strip()})
            return {"passed": False, "failures": failures}
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            ctx.logger.warning("[TestRun] go test timed out")
            return {"passed": False, "failures": []}

    def _run_cargo_test(self, ctx: PhaseContext) -> Optional[Dict]:
        """Run `cargo test`."""
        try:
            result = subprocess.run(
                ["cargo", "test"],
                cwd=str(ctx.project_root),
                capture_output=True,
                text=True,
                timeout=_TEST_TIMEOUT,
            )
            if result.returncode == 0:
                return {"passed": True, "failures": []}
            failures = []
            for line in (result.stdout + result.stderr).splitlines():
                if line.strip().startswith("FAILED"):
                    test_name = line.strip().split()[-1] if line.strip().split() else "unknown"
                    failures.append({"file_path": "src", "test_name": test_name, "error": line.strip()})
            return {"passed": False, "failures": failures}
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            ctx.logger.warning("[TestRun] cargo test timed out")
            return {"passed": False, "failures": []}

    def _run_mvn_test(self, ctx: PhaseContext) -> Optional[Dict]:
        """Run `mvn test -q`."""
        try:
            result = subprocess.run(
                ["mvn", "test", "-q"],
                cwd=str(ctx.project_root),
                capture_output=True,
                text=True,
                timeout=_TEST_TIMEOUT,
            )
            if result.returncode == 0:
                return {"passed": True, "failures": []}
            failures = []
            for line in (result.stdout + result.stderr).splitlines():
                if "FAILED" in line or "ERROR" in line:
                    failures.append({"file_path": "src", "test_name": "mvn", "error": line.strip()})
            return {"passed": False, "failures": failures[:5]}
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            ctx.logger.warning("[TestRun] mvn test timed out")
            return {"passed": False, "failures": []}

    def _run_jest(self, ctx: PhaseContext) -> Optional[Dict]:
        """Run `npx jest --passWithNoTests`."""
        try:
            result = subprocess.run(
                ["npx", "jest", "--passWithNoTests", "--no-coverage"],
                cwd=str(ctx.project_root),
                capture_output=True,
                text=True,
                timeout=_TEST_TIMEOUT,
            )
            if result.returncode == 0:
                return {"passed": True, "failures": []}
            failures = []
            for line in (result.stdout + result.stderr).splitlines():
                m = re.match(r"\s+✕\s+(.+)", line) or re.match(r"\s+×\s+(.+)", line)
                if m:
                    failures.append({"file_path": ".", "test_name": m.group(1).strip(), "error": line.strip()})
            return {"passed": False, "failures": failures}
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            ctx.logger.warning("[TestRun] jest timed out")
            return {"passed": False, "failures": []}

    def _parse_failures(self, output: str) -> List[Dict[str, str]]:
        """Parse pytest --tb=short output into [{file_path, error}]."""
        failures: List[Dict[str, str]] = []
        # Pattern: "FAILED src/foo.py::test_bar - AssertionError: ..."
        for line in output.splitlines():
            m = re.match(r"FAILED\s+([\w/\\.\-]+)::([\w]+)\s+-\s+(.+)", line)
            if m:
                failures.append(
                    {
                        "file_path": m.group(1).replace("\\", "/"),
                        "test_name": m.group(2),
                        "error": m.group(3).strip(),
                    }
                )
        return failures

    def _patch_failure(self, ctx: PhaseContext, failure: Dict[str, str]) -> bool:
        """Patch a single failing file. Returns True if patched successfully."""
        file_path = failure.get("file_path", "")
        error = failure.get("error", "")

        # Determine which source file to patch (not the test file itself, if possible)
        source_path = self._find_source_file(ctx, file_path, error)
        content = ctx.generated_files.get(source_path, "")
        if not content:
            abs_path = ctx.project_root / source_path
            if abs_path.exists():
                content = abs_path.read_text(encoding="utf-8", errors="replace")
        if not content:
            return False

        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
        except ImportError:
            try:
                from backend.utils.domains.auto_generation.code_patcher import CodePatcher
            except ImportError:
                return False

        try:
            patcher = CodePatcher(
                llm_client=ctx.llm_manager.get_client("coder"),
                logger=ctx.logger,
            )
            patched = patcher.edit_existing_file(
                file_path=source_path,
                current_content=content,
                readme=ctx.project_description[:300],
                issues_to_fix=[{"description": f"Test failure in {failure.get('test_name', 'test')}: {error}"}],
            )
            if patched and patched != content:
                self._write_file(ctx, source_path, patched)
                if ctx.run_logger:
                    ctx.run_logger.log_file_written(self.phase_id, source_path, len(patched), "ok", "test failure fix")
                return True
        except Exception as e:
            ctx.logger.warning(f"[TestRun] Patch failed for {source_path}: {e}")
        return False

    def _find_source_file(self, ctx: PhaseContext, test_path: str, error: str) -> str:
        """Heuristic: find the source file corresponding to a test file."""
        # If the test itself is broken, patch it; otherwise find the source
        test_name = Path(test_path).stem
        # e.g. test_converter.py -> converter.py
        source_name = test_name.replace("test_", "").replace("_test", "")
        for path in ctx.generated_files:
            if Path(path).stem == source_name and "test" not in path.lower():
                return path
        return test_path  # fall back to patching the test file
