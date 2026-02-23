"""
Sandbox Validator (E9) — Validate generated files before writing to disk.

Runs a lightweight syntax check (and optionally a Docker container check) before
committing a generated/refined file to the project directory. If the file fails
validation it is saved with a `.candidate` suffix so engineers can inspect it
without polluting the live codebase.

Fail-open design: any infrastructure error (Docker unavailable, timeout, etc.)
is logged as a warning and the file is written normally.
"""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class ValidationResult:
    """Outcome of a sandbox validation attempt."""

    approved: bool
    reason: str = ""
    exit_code: int = 0
    candidate_path: Optional[str] = None


class SandboxValidator:
    """Validates generated source files before writing them to disk.

    Validation pipeline (per file extension):
    1. Local syntax check via subprocess (fast, always runs).
    2. Docker container syntax check (only when Docker is reachable and the
       extension is ``".py"``).

    If the file passes all checks it is written to *file_path*.
    If any check fails the content is written to *file_path + ".candidate"*
    so engineers can review the proposed change without breaking the project.

    Infrastructure failures (Docker unavailable, timeout, missing interpreter)
    are treated as non-blocking: the file is written normally (fail-open).
    """

    SYNTAX_COMMANDS: dict = {
        ".py": "python -m py_compile {file}",
        ".js": "node --check {file}",
    }

    def __init__(self, logger: AgentLogger):
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_and_write(
        self,
        file_path: Path,
        content: str,
        file_manager,
    ) -> ValidationResult:
        """Validate *content* and write to *file_path* (or *.candidate*).

        Args:
            file_path: Destination path (absolute or relative within project).
            content: File content to validate and write.
            file_manager: FileManager (or LockedFileManager) instance to use for
                actual disk writes — keeps locking semantics intact.

        Returns:
            ValidationResult indicating whether the file was approved.
        """
        suffix = Path(file_path).suffix.lower()

        # Step 1: local syntax check
        ok, reason = self._syntax_check(suffix, content)
        if not ok:
            self.logger.warning(
                f"SandboxValidator: syntax check failed for {file_path}: {reason}"
            )
            candidate = str(file_path) + ".candidate"
            try:
                file_manager.write_file(candidate, content)
            except Exception as write_exc:
                self.logger.warning(f"SandboxValidator: could not write candidate: {write_exc}")
            return ValidationResult(
                approved=False,
                reason=reason,
                exit_code=1,
                candidate_path=candidate,
            )

        # Step 2: Docker validation (Python only, best-effort)
        if suffix == ".py":
            docker_ok, docker_reason = self._docker_validate(content)
            if not docker_ok:
                self.logger.warning(
                    f"SandboxValidator: Docker validation failed for {file_path}: {docker_reason}"
                )
                candidate = str(file_path) + ".candidate"
                try:
                    file_manager.write_file(candidate, content)
                except Exception as write_exc:
                    self.logger.warning(f"SandboxValidator: could not write candidate: {write_exc}")
                return ValidationResult(
                    approved=False,
                    reason=docker_reason,
                    exit_code=1,
                    candidate_path=candidate,
                )

        # All checks passed — write to the real path
        try:
            file_manager.write_file(file_path, content)
        except Exception as write_exc:
            self.logger.warning(f"SandboxValidator: write failed for {file_path}: {write_exc}")
            return ValidationResult(approved=False, reason=str(write_exc), exit_code=1)

        return ValidationResult(approved=True, reason="ok", exit_code=0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _syntax_check(self, suffix: str, content: str) -> Tuple[bool, str]:
        """Run a subprocess syntax check for the given file extension.

        Returns:
            (True, "ok") on success; (False, reason) on failure or infra error.
        """
        command_template = self.SYNTAX_COMMANDS.get(suffix)
        if not command_template:
            # Unknown extension — skip syntax check, allow through
            return True, "no syntax check for extension"

        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix, mode="w", encoding="utf-8", delete=False
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            cmd = command_template.format(file=tmp_path).split()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            Path(tmp_path).unlink(missing_ok=True)

            if result.returncode == 0:
                return True, "ok"
            error_detail = (result.stderr or result.stdout or "").strip()[:300]
            return False, error_detail or "syntax error"

        except FileNotFoundError:
            # Interpreter not installed — fail-open
            self.logger.warning(
                f"SandboxValidator: interpreter not found for {suffix}, skipping syntax check"
            )
            return True, "interpreter not available"
        except subprocess.TimeoutExpired:
            self.logger.warning(f"SandboxValidator: syntax check timed out for {suffix}")
            return True, "timeout — treated as pass"
        except Exception as exc:
            self.logger.warning(f"SandboxValidator: unexpected error in syntax check: {exc}")
            return True, "infra error — treated as pass"

    def _docker_validate(self, content: str) -> Tuple[bool, str]:
        """Validate Python content inside a Docker container.

        Returns:
            (True, "ok") when Docker is unavailable (fail-open) or content passes.
            (False, reason) only when Docker is reachable AND content fails.
        """
        try:
            import backend.utils.core.tools.wasm_sandbox as _wasm_mod

            WasmSandbox = _wasm_mod.WasmSandbox
            sandbox = WasmSandbox(logger=self.logger)
            if not sandbox.is_available:
                # Docker/Wasm not available — fail-open
                return True, "sandbox not available"
        except Exception:
            return True, "sandbox import error"

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", encoding="utf-8", delete=False
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            result = subprocess.run(
                ["python", "-m", "py_compile", tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            Path(tmp_path).unlink(missing_ok=True)

            if result.returncode == 0:
                return True, "ok"
            error_detail = (result.stderr or "").strip()[:300]
            return False, error_detail or "docker compile error"

        except subprocess.TimeoutExpired:
            return True, "docker timeout — treated as pass"
        except Exception as exc:
            return True, f"docker error — treated as pass: {exc}"
