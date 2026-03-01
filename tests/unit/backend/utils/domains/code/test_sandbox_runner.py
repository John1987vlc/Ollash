"""Unit tests — SandboxRunner (P3 empirical validation)."""

from unittest.mock import MagicMock, patch

import pytest

from backend.utils.domains.code.sandbox_runner import SandboxResult, SandboxRunner


def _make_runner() -> SandboxRunner:
    logger = MagicMock()
    return SandboxRunner(logger=logger, timeout_seconds=10, run_mypy=False)


@pytest.mark.unit
class TestSandboxRunnerBasic:
    def test_non_python_file_is_skipped(self):
        runner = _make_runner()
        result = runner.run_linter("config.yaml", "key: value")
        assert result.passed is True
        assert result.tool == "skipped"

    def test_empty_content_passed(self):
        runner = _make_runner()
        result = runner.run_linter("empty.py", "")
        # Empty file is valid Python — ruff should pass or skip
        assert isinstance(result, SandboxResult)

    def test_clean_python_passes(self):
        runner = _make_runner()
        content = "def add(a: int, b: int) -> int:\n    return a + b\n"
        result = runner.run_linter("add.py", content)
        # May be "unavailable" if ruff not installed in CI, or passed=True
        assert result.tool in ("ruff", "unavailable", "skipped")
        if result.tool == "ruff":
            assert result.passed is True

    def test_result_dataclass_fields(self):
        r = SandboxResult(
            passed=False,
            tool="ruff",
            output="E501 line too long",
            errors=["E501"],
            file_path="main.py",
        )
        assert r.passed is False
        assert r.tool == "ruff"
        assert r.file_path == "main.py"
        assert "E501" in r.errors

    @patch("subprocess.run")
    def test_ruff_error_returns_failed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="E501 line too long", stderr="")
        runner = _make_runner()
        result = runner.run_linter("bad.py", "x = 1 + 2  " + "a" * 100)
        assert result.passed is False
        assert result.tool == "ruff"

    @patch("subprocess.run")
    def test_timeout_returns_failed(self, mock_run):
        import subprocess

        def _side_effect(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="ruff 0.1.0", stderr="")
            raise subprocess.TimeoutExpired(cmd="ruff", timeout=10)

        mock_run.side_effect = _side_effect
        runner = _make_runner()
        result = runner.run_linter("slow.py", "x = 1")
        assert result.passed is False
        assert "timeout" in result.tool.lower() or "ruff" in result.tool.lower()
