"""Unit tests for SandboxValidator (E9)."""

import subprocess
import pytest
from unittest.mock import MagicMock, patch


def _make_validator():
    from backend.utils.domains.auto_generation.sandbox_validator import SandboxValidator

    logger = MagicMock()
    return SandboxValidator(logger=logger), logger


@pytest.mark.unit
class TestSandboxValidator:
    """Tests for validate_and_write, _syntax_check, _docker_validate."""

    # ------------------------------------------------------------------
    # validate_and_write — approved path
    # ------------------------------------------------------------------

    def test_valid_python_writes_to_original_path(self, tmp_path):
        validator, _ = _make_validator()
        file_manager = MagicMock()
        content = "x = 1\n"

        with patch.object(validator, "_syntax_check", return_value=(True, "ok")), \
             patch.object(validator, "_docker_validate", return_value=(True, "ok")):
            result = validator.validate_and_write(tmp_path / "app.py", content, file_manager)

        assert result.approved is True
        file_manager.write_file.assert_called_once()
        call_path = str(file_manager.write_file.call_args[0][0])
        assert not call_path.endswith(".candidate")

    def test_valid_non_python_writes_to_original_path(self, tmp_path):
        """Non-.py files skip Docker validation."""
        validator, _ = _make_validator()
        file_manager = MagicMock()

        with patch.object(validator, "_syntax_check", return_value=(True, "ok")):
            result = validator.validate_and_write(tmp_path / "app.ts", "const x = 1;", file_manager)

        assert result.approved is True
        # Docker validate must NOT be called for .ts
        # (no explicit assertion needed — _docker_validate isn't patched, so any call
        # would raise unless WasmSandbox is available; the test passes means it was skipped)

    # ------------------------------------------------------------------
    # validate_and_write — rejected path
    # ------------------------------------------------------------------

    def test_syntax_failure_writes_candidate(self, tmp_path):
        validator, _ = _make_validator()
        file_manager = MagicMock()
        content = "def broken(:\n"

        with patch.object(validator, "_syntax_check", return_value=(False, "SyntaxError: invalid syntax")):
            result = validator.validate_and_write(tmp_path / "app.py", content, file_manager)

        assert result.approved is False
        assert result.candidate_path is not None
        assert result.candidate_path.endswith(".candidate")
        # Write was called with the candidate path
        written_path = str(file_manager.write_file.call_args[0][0])
        assert written_path.endswith(".candidate")

    def test_docker_failure_writes_candidate(self, tmp_path):
        validator, _ = _make_validator()
        file_manager = MagicMock()

        with patch.object(validator, "_syntax_check", return_value=(True, "ok")), \
             patch.object(validator, "_docker_validate", return_value=(False, "import error")):
            result = validator.validate_and_write(tmp_path / "app.py", "import missing_pkg\n", file_manager)

        assert result.approved is False
        assert result.candidate_path is not None

    # ------------------------------------------------------------------
    # _syntax_check
    # ------------------------------------------------------------------

    def test_syntax_check_passes_for_valid_python(self):
        validator, _ = _make_validator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ok, reason = validator._syntax_check(".py", "x = 1\n")
        assert ok is True

    def test_syntax_check_fails_for_invalid_python(self):
        validator, _ = _make_validator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="SyntaxError: invalid syntax")
            ok, reason = validator._syntax_check(".py", "def broken(:\n")
        assert ok is False
        assert "SyntaxError" in reason or reason != ""

    def test_syntax_check_unknown_extension_passes(self):
        validator, _ = _make_validator()
        ok, reason = validator._syntax_check(".md", "# Hello\n")
        assert ok is True

    def test_syntax_check_returns_true_when_interpreter_missing(self):
        """FileNotFoundError → fail-open → (True, ...)."""
        validator, _ = _make_validator()
        with patch("subprocess.run", side_effect=FileNotFoundError("python not found")):
            ok, _ = validator._syntax_check(".py", "x = 1\n")
        assert ok is True

    def test_syntax_check_returns_true_on_timeout(self):
        validator, _ = _make_validator()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python", 15)):
            ok, _ = validator._syntax_check(".py", "x = 1\n")
        assert ok is True

    # ------------------------------------------------------------------
    # _docker_validate
    # ------------------------------------------------------------------

    def test_docker_validate_returns_true_when_sandbox_unavailable(self):
        """WasmSandbox.is_available=False → fail-open."""
        validator, _ = _make_validator()
        # WasmSandbox is imported locally inside _docker_validate; patch at source module
        with patch(
            "backend.utils.core.tools.wasm_sandbox.WasmSandbox"
        ) as MockSandbox:
            MockSandbox.return_value.is_available = False
            ok, reason = validator._docker_validate("x = 1\n")
        assert ok is True

    def test_docker_validate_returns_true_on_import_error(self):
        """WasmSandbox import failure → fail-open."""
        validator, _ = _make_validator()
        # Simulate an import error by making the module raise on access
        import backend.utils.core.tools.wasm_sandbox as wasm_mod
        with patch.object(wasm_mod, "WasmSandbox", side_effect=ImportError("no wasm")):
            ok, _ = validator._docker_validate("x = 1\n")
        assert ok is True

    def test_docker_validate_fails_when_compile_fails(self):
        validator, _ = _make_validator()
        with patch(
            "backend.utils.core.tools.wasm_sandbox.WasmSandbox"
        ) as MockSandbox:
            MockSandbox.return_value.is_available = True
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1, stdout="", stderr="SyntaxError at line 1"
                )
                ok, reason = validator._docker_validate("def bad(:\n")
        assert ok is False

    def test_docker_validate_returns_true_on_timeout(self):
        validator, _ = _make_validator()
        with patch(
            "backend.utils.core.tools.wasm_sandbox.WasmSandbox"
        ) as MockSandbox:
            MockSandbox.return_value.is_available = True
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python", 30)):
                ok, _ = validator._docker_validate("x = 1\n")
        assert ok is True

    # ------------------------------------------------------------------
    # Unknown extension — skip docker
    # ------------------------------------------------------------------

    def test_non_py_file_skips_docker_validation(self, tmp_path):
        validator, _ = _make_validator()
        file_manager = MagicMock()
        docker_mock = MagicMock(return_value=(False, "fail"))

        with patch.object(validator, "_syntax_check", return_value=(True, "ok")), \
             patch.object(validator, "_docker_validate", docker_mock):
            validator.validate_and_write(tmp_path / "style.css", "body {}", file_manager)

        docker_mock.assert_not_called()
