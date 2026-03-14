"""Unit tests for QualityGate (E3)."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.unit
class TestQualityGate:
    """Tests for QualityGate.run_quality_check and run_linter."""

    @pytest.fixture
    def mock_logger(self):
        return MagicMock()

    def test_run_linter_returns_zero_errors_on_clean_output(self, mock_logger, tmp_path):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate

        gate = QualityGate(logger=mock_logger)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            errors, output = gate.run_linter(tmp_path, "ruff check .")

        assert errors == 0

    def test_run_linter_counts_errors_from_output(self, mock_logger, tmp_path):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate

        gate = QualityGate(logger=mock_logger)
        linter_output = "src/app.py:10:5: E501 line too long\nsrc/app.py:20:1: F401 unused import\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=linter_output, stderr="")
            errors, output = gate.run_linter(tmp_path, "ruff check .")

        assert errors == 2

    def test_run_linter_returns_zero_when_not_installed(self, mock_logger, tmp_path):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate

        gate = QualityGate(logger=mock_logger)
        with patch("subprocess.run", side_effect=FileNotFoundError("ruff not found")):
            errors, output = gate.run_linter(tmp_path, "ruff check .")

        assert errors == 0
        assert "not found" in output

    def test_run_quality_check_passes_when_all_ok(self, mock_logger, tmp_path):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate
        from backend.utils.core.tools.wasm_sandbox import TestResult

        gate = QualityGate(logger=mock_logger)
        passing_test_result = TestResult(
            success=True,
            exit_code=0,
            stdout="5 passed",
            stderr="",
            duration_seconds=1.0,
            tests_passed=5,
            tests_failed=0,
        )

        with (
            patch.object(gate, "run_linter", return_value=(0, "")),
            patch.object(gate, "_run_tests", new=MagicMock(return_value=passing_test_result)),
        ):
            report = gate.run_quality_check(tmp_path)

        assert report.overall_pass is True
        assert report.tests_failed == 0
        assert report.linter_errors == 0

    def test_run_quality_check_fails_when_tests_fail(self, mock_logger, tmp_path):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate
        from backend.utils.core.tools.wasm_sandbox import TestResult

        gate = QualityGate(logger=mock_logger)
        failing_test_result = TestResult(
            success=False,
            exit_code=1,
            stdout="2 failed",
            stderr="",
            duration_seconds=1.0,
            tests_passed=3,
            tests_failed=2,
        )

        with (
            patch.object(gate, "run_linter", return_value=(0, "")),
            patch.object(gate, "_run_tests", new=MagicMock(return_value=failing_test_result)),
        ):
            report = gate.run_quality_check(tmp_path)

        assert report.overall_pass is False
        assert report.tests_failed == 2
        assert len(report.failure_reasons) > 0

    def test_run_quality_check_fails_when_lint_errors(self, mock_logger, tmp_path):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate
        from backend.utils.core.tools.wasm_sandbox import TestResult

        gate = QualityGate(logger=mock_logger)
        passing_test_result = TestResult(
            success=True,
            exit_code=0,
            stdout="1 passed",
            stderr="",
            duration_seconds=0.5,
            tests_passed=1,
            tests_failed=0,
        )

        with (
            patch.object(gate, "run_linter", return_value=(3, "3 errors found")),
            patch.object(gate, "_run_tests", new=MagicMock(return_value=passing_test_result)),
        ):
            report = gate.run_quality_check(tmp_path)

        assert report.overall_pass is False
        assert report.linter_errors == 3

    def test_parse_pytest_output_extracts_counts(self):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate

        passed, failed = QualityGate._parse_pytest_output(
            "======================== 5 passed, 2 failed in 3.14s ========================"
        )
        assert passed == 5
        assert failed == 2

    def test_parse_pytest_output_all_passed(self):
        from backend.utils.domains.auto_generation.quality_gate import QualityGate

        passed, failed = QualityGate._parse_pytest_output("3 passed in 1.00s")
        assert passed == 3
        assert failed == 0
