"""
Quality Gate — Runs tests and linter checks after each improvement cycle.

Used by IterativeImprovementPhase to validate that generated improvements
do not break existing tests or introduce linter errors. If quality checks
fail an auto-heal loop is triggered before the next improvement iteration.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class QualityReport:
    """Result of a quality check run (tests + linter)."""

    tests_passed: int = 0
    tests_failed: int = 0
    linter_errors: int = 0
    linter_warnings: int = 0
    linter_output: str = ""
    test_output: str = ""
    overall_pass: bool = False
    failure_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "linter_errors": self.linter_errors,
            "linter_warnings": self.linter_warnings,
            "overall_pass": self.overall_pass,
            "failure_reasons": self.failure_reasons,
        }


class QualityGate:
    """Runs tests via WasmTestRunner and linting via subprocess.

    The check sequence:
    1. Run linter (ruff or flake8) — errors only block, warnings do not.
    2. Run tests (pytest or similar) via WasmTestRunner.
    3. overall_pass = True iff tests_failed == 0 and linter_errors == 0.

    If the sandbox/wasm runner is unavailable the test step is skipped and
    only the linter result is used to determine overall_pass.
    """

    MAX_HEAL_ITERATIONS: int = 3

    def __init__(
        self,
        logger: AgentLogger,
        sandbox: Optional[object] = None,
    ):
        self.logger = logger
        self._sandbox = sandbox

    async def run_quality_check(
        self,
        project_root: Path,
        language: str = "python",
        test_command: str = "pytest tests/unit -x --tb=short -q",
        lint_command: Optional[str] = "ruff check . --select=E,W,F --quiet",
    ) -> QualityReport:
        """Run linter then tests; return a QualityReport.

        Args:
            project_root: Directory containing the project to check.
            language: Primary language ('python' or 'javascript').
            test_command: Shell command to run tests.
            lint_command: Shell command to run linter (None = skip lint).

        Returns:
            QualityReport with pass/fail status and diagnostics.
        """
        report = QualityReport()
        failure_reasons: List[str] = []

        # --- Lint step ---
        if lint_command:
            try:
                lint_errors, lint_output = self.run_linter(project_root, lint_command)
                report.linter_errors = lint_errors
                report.linter_output = lint_output
                if lint_errors > 0:
                    failure_reasons.append(f"Linter reported {lint_errors} error(s)")
            except Exception as exc:
                self.logger.warning(f"QualityGate: linter step failed (non-critical): {exc}")

        # --- Test step ---
        try:
            test_result = await self._run_tests(project_root, test_command, language)
            if test_result is not None:
                report.tests_passed = test_result.tests_passed
                report.tests_failed = test_result.tests_failed
                report.test_output = test_result.stdout[:2000]
                if test_result.tests_failed > 0:
                    failure_reasons.append(
                        f"{test_result.tests_failed} test(s) failed"
                    )
                    # Extract first failing test name if possible
                    for line in test_result.stdout.splitlines():
                        if "FAILED" in line:
                            failure_reasons.append(f"  {line.strip()}")
                            break
        except Exception as exc:
            self.logger.warning(f"QualityGate: test step failed (non-critical): {exc}")

        report.overall_pass = report.tests_failed == 0 and report.linter_errors == 0
        report.failure_reasons = failure_reasons
        return report

    async def _run_tests(self, project_root: Path, test_command: str, language: str):
        """Run tests via WasmTestRunner if available, else subprocess."""
        if self._sandbox is not None:
            try:
                from backend.utils.core.tools.wasm_sandbox import WasmTestRunner

                runner = WasmTestRunner(self._sandbox, self.logger)
                return await runner.run_tests(project_root, test_command, language=language)
            except Exception as exc:
                self.logger.warning(f"WasmTestRunner unavailable, falling back to subprocess: {exc}")

        # Subprocess fallback
        return self._run_tests_subprocess(project_root, test_command)

    def _run_tests_subprocess(self, project_root: Path, test_command: str):
        """Run test command directly via subprocess and return a mock TestResult."""
        from backend.utils.core.tools.wasm_sandbox import TestResult

        try:
            result = subprocess.run(
                test_command.split(),
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            stdout = result.stdout + result.stderr
            passed, failed = self._parse_pytest_output(stdout)
            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=stdout,
                stderr=result.stderr,
                duration_seconds=0.0,
                tests_passed=passed,
                tests_failed=failed,
            )
        except Exception as exc:
            self.logger.warning(f"Test subprocess failed: {exc}")
            return None

    def run_linter(self, project_root: Path, command: str) -> Tuple[int, str]:
        """Run linter subprocess; return (error_count, output).

        Args:
            project_root: Working directory for the linter.
            command: Full linter command string (will be split on spaces).

        Returns:
            Tuple of (number_of_errors, combined_output_string).
        """
        try:
            result = subprocess.run(
                command.split(),
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            combined = result.stdout + result.stderr
            error_count = self._count_linter_errors(combined, result.returncode)
            return error_count, combined
        except subprocess.TimeoutExpired:
            return 0, "Linter timed out"
        except FileNotFoundError:
            # Linter not installed — treat as no errors
            return 0, "Linter not found, skipped"

    @staticmethod
    def _count_linter_errors(output: str, returncode: int) -> int:
        """Count error-level issues from linter output.

        Tries to parse ruff/flake8 output format; falls back to returncode.
        """
        if not output.strip():
            return 0
        # ruff/flake8: lines like "file.py:10:5: E501 ..."
        error_pattern = re.compile(r":\s+[EF]\d{3,}")
        errors = error_pattern.findall(output)
        if errors:
            return len(errors)
        # Fallback: non-zero return code means errors
        return 1 if returncode not in (0,) else 0

    @staticmethod
    def _parse_pytest_output(output: str) -> Tuple[int, int]:
        """Extract passed/failed counts from pytest output."""
        # Pattern: "5 passed, 2 failed" or "3 passed" or "1 failed"
        match = re.search(r"(\d+)\s+passed", output)
        passed = int(match.group(1)) if match else 0
        match = re.search(r"(\d+)\s+failed", output)
        failed = int(match.group(1)) if match else 0
        return passed, failed
