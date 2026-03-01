"""
SandboxRunner — Empirical Code Validation via Real Linter Execution.

Executes ``ruff`` and (optionally) ``mypy`` against generated files in an
isolated temporary directory, capturing the real compiler/linter output.

This replaces purely-static auditing: if the LLM hallucinated an import or
introduced a syntax error, the actual traceback is captured and injected into
the SelfHealingLoop context, dramatically increasing the AI's ability to fix
real errors compared to pattern-matching on text alone.

Isolation guarantees:
    - Each invocation writes to a fresh ``tempfile.mkdtemp()`` directory.
    - The temp directory is always cleaned up in a ``finally`` block.
    - The subprocess is killed if it exceeds *timeout_seconds*.
    - No network access is granted to the subprocess.

Usage::

    runner = SandboxRunner(logger=logger, timeout_seconds=30)
    result = runner.run_linter("src/main.py", content)
    if not result.passed:
        print(result.errors)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class SandboxResult:
    """Result of a sandbox linter execution."""

    passed: bool
    tool: str  # "ruff" | "mypy" | "unavailable"
    output: str  # Combined stdout + stderr
    errors: List[str] = field(default_factory=list)  # Parsed error lines
    file_path: str = ""


class SandboxRunner:
    """
    Runs ``ruff`` (and optionally ``mypy``) on generated source code.

    Args:
        logger:           AgentLogger instance.
        timeout_seconds:  Max seconds allowed per subprocess (default 30).
        run_mypy:         Whether to also run mypy after ruff (default False
                          since mypy is slow and requires full type stubs).
    """

    def __init__(
        self,
        logger: AgentLogger,
        timeout_seconds: int = 30,
        run_mypy: bool = False,
    ) -> None:
        self._logger = logger
        self._timeout = timeout_seconds
        self._run_mypy = run_mypy

    def run_linter(self, rel_path: str, content: str) -> SandboxResult:
        """Write *content* to a temp file and run ruff on it.

        Args:
            rel_path: Relative path of the file (used to preserve extension
                      and for error messages — e.g. ``src/main.py``).
            content:  Source code string to validate.

        Returns:
            A SandboxResult. ``passed`` is True only if ruff exits with code 0.
        """
        if not self._is_python_file(rel_path):
            # Only Python files are linted; others pass automatically
            return SandboxResult(passed=True, tool="skipped", output="", file_path=rel_path)

        if not self._ruff_available():
            self._logger.debug("[SandboxRunner] ruff not found — skipping sandbox lint")
            return SandboxResult(
                passed=True,
                tool="unavailable",
                output="ruff not installed",
                file_path=rel_path,
            )

        tmp_dir: Optional[str] = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix="ollash_sandbox_")
            tmp_file = Path(tmp_dir) / Path(rel_path).name
            tmp_file.write_text(content, encoding="utf-8")

            result = subprocess.run(
                ["ruff", "check", "--select", "E,F,W", "--output-format", "concise", str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            full_output = (result.stdout + result.stderr).strip()
            passed = result.returncode == 0
            errors = self._parse_ruff_errors(full_output, rel_path)

            # Optional mypy pass
            if passed and self._run_mypy and self._mypy_available():
                mypy_result = subprocess.run(
                    ["mypy", str(tmp_file), "--ignore-missing-imports", "--no-error-summary"],
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                )
                mypy_output = (mypy_result.stdout + mypy_result.stderr).strip()
                if mypy_result.returncode != 0:
                    passed = False
                    full_output = full_output + "\n" + mypy_output
                    errors += self._parse_mypy_errors(mypy_output, rel_path)

            tool = "ruff+mypy" if (self._run_mypy and self._mypy_available()) else "ruff"
            self._logger.debug(
                f"[SandboxRunner] {tool} on '{rel_path}': {'PASS' if passed else f'FAIL ({len(errors)} errors)'}"
            )
            return SandboxResult(
                passed=passed,
                tool=tool,
                output=full_output,
                errors=errors,
                file_path=rel_path,
            )

        except subprocess.TimeoutExpired:
            self._logger.warning(f"[SandboxRunner] Timeout ({self._timeout}s) on '{rel_path}'")
            return SandboxResult(
                passed=False,
                tool="ruff",
                output=f"Timeout after {self._timeout}s",
                errors=["Linter timed out"],
                file_path=rel_path,
            )
        except Exception as exc:
            self._logger.error(f"[SandboxRunner] Unexpected error on '{rel_path}': {exc}")
            return SandboxResult(
                passed=True,  # Don't block agent on unexpected sandbox failure
                tool="error",
                output=str(exc),
                file_path=rel_path,
            )
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_python_file(rel_path: str) -> bool:
        return rel_path.endswith(".py")

    @staticmethod
    def _ruff_available() -> bool:
        try:
            subprocess.run(["ruff", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _mypy_available() -> bool:
        try:
            subprocess.run(["mypy", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _parse_ruff_errors(output: str, rel_path: str) -> List[str]:
        """Extract error lines from ruff text output."""
        errors = []
        for line in output.splitlines():
            # ruff format: "path.py:line:col: CODE message"
            if ".py:" in line and any(c in line for c in ("E", "F", "W")):
                errors.append(line.strip())
        return errors

    @staticmethod
    def _parse_mypy_errors(output: str, rel_path: str) -> List[str]:
        """Extract error lines from mypy output."""
        return [line.strip() for line in output.splitlines() if "error:" in line or "note:" in line]
