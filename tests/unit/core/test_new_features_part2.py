"""
Unit tests for new features modules (Part 2).

Tests:
- CostAnalyzer (cost_analyzer.py)
- CICDHealer (cicd_healer.py)
- ExportManager (export_manager.py)
- PromptTuner & FeedbackStore (prompt_tuner.py)
- DeepLicenseScanner (deep_license_scanner.py)
- UIAnalyzer (ui_analyzer.py)
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from backend.utils.core.cicd_healer import CICDHealer, CIFailureAnalysis
from backend.utils.core.cost_analyzer import (
    CostAnalyzer,
    CostReport,
)
from backend.utils.core.deep_license_scanner import (
    CompatibilityReport,
    DeepLicenseScanner,
    DependencyLicense,
    LicenseConflict,
)
from backend.utils.core.export_manager import ExportManager
from backend.utils.core.prompt_tuner import FeedbackEntry, FeedbackStore, PromptTuner
from backend.utils.core.ui_analyzer import UIAnalyzer, UIAnalysisReport, UIIssue


# =============================================================================
# CostAnalyzer Tests
# =============================================================================


class TestCostAnalyzer:
    """Test suite for CostAnalyzer."""

    def test_record_usage_stores_records(self):
        """Test that record_usage correctly stores usage records."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage(
            model_name="llama3:8b",
            phase_name="FileContentGenerationPhase",
            prompt_tokens=1000,
            completion_tokens=500,
            task_type="generation",
        )

        assert len(analyzer._records) == 1
        record = analyzer._records[0]
        assert record.model_name == "llama3:8b"
        assert record.phase_name == "FileContentGenerationPhase"
        assert record.prompt_tokens == 1000
        assert record.completion_tokens == 500
        assert record.total_tokens == 1500
        assert record.task_type == "generation"

    def test_get_usage_by_model_aggregation(self):
        """Test usage aggregation by model."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage("llama3:8b", "Phase1", 1000, 500)
        analyzer.record_usage("llama3:8b", "Phase2", 800, 400)
        analyzer.record_usage("mistral:latest", "Phase1", 600, 300)

        by_model = analyzer.get_usage_by_model()

        assert "llama3:8b" in by_model
        assert by_model["llama3:8b"]["prompt_tokens"] == 1800
        assert by_model["llama3:8b"]["completion_tokens"] == 900
        assert by_model["llama3:8b"]["total_tokens"] == 2700
        assert by_model["llama3:8b"]["requests"] == 2

        assert "mistral:latest" in by_model
        assert by_model["mistral:latest"]["total_tokens"] == 900
        assert by_model["mistral:latest"]["requests"] == 1

    def test_get_usage_by_phase_aggregation(self):
        """Test usage aggregation by phase."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage("llama3:8b", "ReadmeGenerationPhase", 500, 200)
        analyzer.record_usage("mistral:latest", "ReadmeGenerationPhase", 400, 150)
        analyzer.record_usage("llama3:8b", "FileContentGenerationPhase", 1000, 500)

        by_phase = analyzer.get_usage_by_phase()

        assert "ReadmeGenerationPhase" in by_phase
        assert by_phase["ReadmeGenerationPhase"]["prompt_tokens"] == 900
        assert by_phase["ReadmeGenerationPhase"]["completion_tokens"] == 350
        assert by_phase["ReadmeGenerationPhase"]["total_tokens"] == 1250
        assert by_phase["ReadmeGenerationPhase"]["requests"] == 2

        assert "FileContentGenerationPhase" in by_phase
        assert by_phase["FileContentGenerationPhase"]["total_tokens"] == 1500
        assert by_phase["FileContentGenerationPhase"]["requests"] == 1

    def test_get_phase_efficiencies_calculation(self):
        """Test phase efficiency metrics calculation."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage("llama3:8b", "Phase1", 1000, 500)
        analyzer.record_usage("llama3:8b", "Phase1", 800, 400)
        analyzer.record_usage("mistral:latest", "Phase1", 200, 100)

        efficiencies = analyzer.get_phase_efficiencies()

        assert len(efficiencies) == 1
        phase_eff = efficiencies[0]
        assert phase_eff.phase_name == "Phase1"
        assert phase_eff.total_tokens == 3000
        assert phase_eff.request_count == 3
        assert phase_eff.avg_tokens_per_request == 1000.0
        assert phase_eff.primary_model == "llama3:8b"  # Most tokens
        assert set(phase_eff.models_used) == {"llama3:8b", "mistral:latest"}

    def test_suggest_downgrades_lightweight_phases(self):
        """Test that suggest_downgrades recommends lighter models for lightweight phases."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        # Use expensive model for lightweight phase
        analyzer.record_usage("llama3:70b", "ReadmeGenerationPhase", 1000, 500)
        analyzer.record_usage("llama3:70b", "ReadmeGenerationPhase", 800, 400)

        suggestions = analyzer.suggest_downgrades()

        assert len(suggestions) > 0
        suggestion = suggestions[0]
        assert suggestion.current_model == "llama3:70b"
        assert suggestion.suggested_model == "ministral-3:8b"
        assert suggestion.phase == "ReadmeGenerationPhase"
        assert suggestion.estimated_savings_pct > 0
        assert "lightweight phase" in suggestion.reason.lower()

    def test_suggest_downgrades_low_token_usage(self):
        """Test suggestions for phases with low token usage."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        # Use expensive model with very low token usage
        analyzer.record_usage("mixtral:8x7b", "CustomPhase", 100, 50)
        analyzer.record_usage("mixtral:8x7b", "CustomPhase", 150, 50)

        suggestions = analyzer.suggest_downgrades()

        # Should suggest downgrade due to low avg tokens
        assert len(suggestions) > 0
        suggestion = suggestions[0]
        assert suggestion.current_model == "mixtral:8x7b"
        assert "Low token usage" in suggestion.reason

    def test_get_report_generates_complete_report(self):
        """Test that get_report generates a complete cost report."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage("llama3:8b", "Phase1", 1000, 500)
        analyzer.record_usage("llama3:70b", "ReadmeGenerationPhase", 800, 400)

        report = analyzer.get_report()

        assert isinstance(report, CostReport)
        assert report.total_tokens == 2700
        assert report.total_prompt_tokens == 1800
        assert report.total_completion_tokens == 900
        assert report.total_requests == 2
        assert len(report.usage_by_model) == 2
        assert len(report.usage_by_phase) == 2
        assert len(report.phase_efficiencies) == 2
        assert report.timestamp != ""

    def test_reset_clears_records(self):
        """Test that reset clears all usage records."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage("llama3:8b", "Phase1", 1000, 500)
        analyzer.record_usage("mistral:latest", "Phase2", 800, 400)

        assert len(analyzer._records) == 2

        analyzer.reset()

        assert len(analyzer._records) == 0
        by_model = analyzer.get_usage_by_model()
        assert len(by_model) == 0

    def test_cost_report_to_dict_serialization(self):
        """Test CostReport.to_dict serialization."""
        logger = MagicMock()
        analyzer = CostAnalyzer(logger)

        analyzer.record_usage("llama3:8b", "Phase1", 1000, 500)

        report = analyzer.get_report()
        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert "total_tokens" in report_dict
        assert report_dict["total_tokens"] == 1500
        assert "usage_by_model" in report_dict
        assert "usage_by_phase" in report_dict
        assert "phase_efficiencies" in report_dict
        assert "suggestions" in report_dict
        assert "timestamp" in report_dict

        # Check phase_efficiencies structure
        assert len(report_dict["phase_efficiencies"]) == 1
        pe = report_dict["phase_efficiencies"][0]
        assert "phase" in pe
        assert "total_tokens" in pe
        assert "requests" in pe
        assert "avg_tokens" in pe
        assert "primary_model" in pe


# =============================================================================
# CICDHealer Tests
# =============================================================================


class TestCICDHealer:
    """Test suite for CICDHealer."""

    def test_analyze_failure_detects_dependency_errors(self):
        """Test detection of ModuleNotFoundError dependency errors."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        workflow_log = """
        ##[error] in step 'Install dependencies'
        ModuleNotFoundError: No module named 'flask'
        ERROR: Failed to install requirements
        """

        analysis = healer.analyze_failure(workflow_log, "CI Pipeline")

        assert isinstance(analysis, CIFailureAnalysis)
        assert analysis.workflow_name == "CI Pipeline"
        assert analysis.category == "dependency"
        assert any("flask" in fix for fix in analysis.suggested_fixes)
        assert "Add 'flask' to requirements.txt" in analysis.suggested_fixes

    def test_analyze_failure_detects_build_errors(self):
        """Test detection of SyntaxError build errors."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        workflow_log = """
        File "main.py", line 10
          def foo(
                ^
        SyntaxError: unexpected EOF while parsing
        """

        analysis = healer.analyze_failure(workflow_log)

        assert analysis.category == "build"
        assert any("syntax" in fix.lower() for fix in analysis.suggested_fixes)

    def test_analyze_failure_detects_test_failures(self):
        """Test detection of test failures."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        workflow_log = """
        FAILED tests/test_main.py::test_feature - AssertionError
        ERROR: Tests failed
        """

        analysis = healer.analyze_failure(workflow_log, "Test Suite")

        assert analysis.category == "test"
        assert analysis.workflow_name == "Test Suite"
        assert any("test" in fix.lower() for fix in analysis.suggested_fixes)

    def test_analyze_failure_detects_lint_errors(self):
        """Test detection of lint errors."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        workflow_log = """
        ruff check failed with 5 errors
        ERROR: Linting failed
        """

        analysis = healer.analyze_failure(workflow_log)

        assert analysis.category == "lint"
        assert any("lint" in fix.lower() for fix in analysis.suggested_fixes)

    def test_extract_errors_from_log_lines(self):
        """Test _extract_errors extracts error lines."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        log = """
        INFO: Starting build
        ERROR: Build failed
        FATAL: Unrecoverable error
        WARNING: Deprecated feature
        Exception: Something went wrong
        """

        errors = healer._extract_errors(log)

        assert len(errors) >= 3
        assert any("Build failed" in e for e in errors)
        assert any("Unrecoverable error" in e for e in errors)
        assert any("Something went wrong" in e for e in errors)

    def test_identify_failure_step_github_actions_format(self):
        """Test _identify_failure_step from GitHub Actions format."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        log = "##[error] Something failed in step 'Run tests'"

        step = healer._identify_failure_step(log)

        assert step == "Run tests"

    def test_identify_failure_step_generic_format(self):
        """Test _identify_failure_step from generic format."""
        logger = MagicMock()
        healer = CICDHealer(logger)

        log = "Step 3/5: Build application\nERROR: Build failed"

        step = healer._identify_failure_step(log)

        assert "3/5" in step

    def test_ci_failure_analysis_to_dict_serialization(self):
        """Test CIFailureAnalysis.to_dict serialization."""
        analysis = CIFailureAnalysis(
            workflow_name="CI",
            failure_step="Build",
            error_messages=["Error 1", "Error 2"],
            root_cause="Build error",
            category="build",
            suggested_fixes=["Fix 1"],
            affected_files=["main.py"],
            confidence=0.8,
        )

        result = analysis.to_dict()

        assert isinstance(result, dict)
        assert result["workflow_name"] == "CI"
        assert result["failure_step"] == "Build"
        assert len(result["error_messages"]) == 2
        assert result["root_cause"] == "Build error"
        assert result["category"] == "build"
        assert result["confidence"] == 0.8
        assert "main.py" in result["affected_files"]


# =============================================================================
# ExportManager Tests
# =============================================================================


class TestExportManager:
    """Test suite for ExportManager."""

    def test_export_zip_creates_zip_file(self, tmp_path):
        """Test that export_zip creates a zip archive."""
        logger = MagicMock()
        command_executor = MagicMock()
        manager = ExportManager(command_executor, logger)

        # Create a test project
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text("test content")

        output_path = manager.export_zip(project_dir, tmp_path)

        assert output_path.exists()
        assert output_path.suffix == ".zip"
        assert output_path.name == "test_project.zip"

    def test_export_zip_default_output_dir(self, tmp_path):
        """Test export_zip uses parent directory as default output dir."""
        logger = MagicMock()
        command_executor = MagicMock()
        manager = ExportManager(command_executor, logger)

        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / "file.txt").write_text("content")

        output_path = manager.export_zip(project_dir)

        # Output should be in parent (tmp_path)
        assert output_path.parent == tmp_path

    def test_get_supported_targets_returns_expected_targets(self):
        """Test get_supported_targets returns expected export targets."""
        logger = MagicMock()
        command_executor = MagicMock()
        manager = ExportManager(command_executor, logger)

        targets = manager.get_supported_targets()

        assert isinstance(targets, dict)
        assert "zip" in targets
        assert "github" in targets
        assert "gitlab" in targets
        assert "vercel" in targets
        assert "railway" in targets
        assert "fly" in targets

        # Check descriptions
        assert "ZIP" in targets["zip"] or "zip" in targets["zip"].lower()
        assert "GitHub" in targets["github"]


# =============================================================================
# PromptTuner & FeedbackStore Tests
# =============================================================================


class TestFeedbackStore:
    """Test suite for FeedbackStore."""

    def test_save_and_query_with_filters(self, tmp_path):
        """Test FeedbackStore save and query with filters."""
        store = FeedbackStore(tmp_path)

        entry1 = FeedbackEntry(
            prompt_id="prompt_a",
            original_output="output1",
            user_correction="correction1",
            rating=0.5,
            phase_name="Phase1",
        )
        entry2 = FeedbackEntry(
            prompt_id="prompt_b",
            original_output="output2",
            user_correction="correction2",
            rating=0.8,
            phase_name="Phase2",
        )
        entry3 = FeedbackEntry(
            prompt_id="prompt_a",
            original_output="output3",
            user_correction="correction3",
            rating=0.9,
            phase_name="Phase1",
        )

        store.save(entry1)
        store.save(entry2)
        store.save(entry3)

        # Query by prompt_id
        results = store.query(prompt_id="prompt_a")
        assert len(results) == 2

        # Query by min_rating
        results = store.query(min_rating=0.7)
        assert len(results) == 2
        assert all(e.rating >= 0.7 for e in results)

        # Query by phase_name
        results = store.query(phase_name="Phase1")
        assert len(results) == 2

        # Combined filters
        results = store.query(prompt_id="prompt_a", min_rating=0.8)
        assert len(results) == 1
        assert results[0].rating == 0.9

    def test_get_avg_rating(self, tmp_path):
        """Test FeedbackStore get_avg_rating calculation."""
        store = FeedbackStore(tmp_path)

        store.save(FeedbackEntry("prompt_a", "out1", "corr1", 0.6))
        store.save(FeedbackEntry("prompt_a", "out2", "corr2", 0.8))
        store.save(FeedbackEntry("prompt_b", "out3", "corr3", 1.0))

        avg_a = store.get_avg_rating("prompt_a")
        assert avg_a == 0.7

        avg_b = store.get_avg_rating("prompt_b")
        assert avg_b == 1.0

        avg_unknown = store.get_avg_rating("unknown")
        assert avg_unknown == 0.5  # Default

    def test_feedback_store_persistence(self, tmp_path):
        """Test that feedback persists across FeedbackStore instances."""
        store1 = FeedbackStore(tmp_path)
        store1.save(FeedbackEntry("prompt_x", "out", "corr", 0.7))

        # Create new instance pointing to same directory
        store2 = FeedbackStore(tmp_path)
        results = store2.query(prompt_id="prompt_x")

        assert len(results) == 1
        assert results[0].rating == 0.7


class TestPromptTuner:
    """Test suite for PromptTuner."""

    def test_record_feedback(self, tmp_path):
        """Test PromptTuner record_feedback stores entry."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        tuner.record_feedback(
            prompt_id="test_prompt",
            output="original output",
            correction="corrected output",
            rating=0.6,
            phase_name="TestPhase",
            file_path="test.py",
            language="python",
        )

        results = store.query(prompt_id="test_prompt")
        assert len(results) == 1
        entry = results[0]
        assert entry.rating == 0.6
        assert entry.phase_name == "TestPhase"
        assert entry.language == "python"

    def test_get_few_shot_examples_returns_corrections(self, tmp_path):
        """Test get_few_shot_examples returns corrections with rating < 0.7."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        # Add entries with different ratings
        tuner.record_feedback("prompt_1", "bad output", "good output", 0.5)
        tuner.record_feedback("prompt_1", "another bad", "another good", 0.6)
        tuner.record_feedback("prompt_1", "perfect", "perfect", 1.0)  # Should be excluded

        examples = tuner.get_few_shot_examples("prompt_1", max_examples=5)

        # Should return only entries with rating < 0.7
        assert len(examples) == 2
        assert all("original" in ex and "corrected" in ex for ex in examples)

    def test_get_few_shot_examples_max_limit(self, tmp_path):
        """Test get_few_shot_examples respects max_examples limit."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        # Add many corrections
        for i in range(10):
            tuner.record_feedback("prompt_1", f"output{i}", f"correction{i}", 0.5)

        examples = tuner.get_few_shot_examples("prompt_1", max_examples=3)

        assert len(examples) == 3

    def test_get_adjusted_prompt_appends_examples(self, tmp_path):
        """Test get_adjusted_prompt appends few-shot examples."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        base_prompt = "Generate code for this feature."

        # No feedback yet - should return base prompt
        adjusted = tuner.get_adjusted_prompt(base_prompt, "prompt_1")
        assert adjusted == base_prompt

        # Add feedback
        tuner.record_feedback("prompt_1", "bad code", "good code", 0.5)

        adjusted = tuner.get_adjusted_prompt(base_prompt, "prompt_1")

        # Should contain base prompt and examples
        assert "Generate code for this feature." in adjusted
        assert "Previous corrections" in adjusted
        assert "Correction 1" in adjusted

    def test_adjust_temperature_for_low_ratings(self, tmp_path):
        """Test adjust_temperature decreases temp for low ratings."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        # Add low-rating feedback
        tuner.record_feedback("prompt_low", "out", "corr", 0.2)
        tuner.record_feedback("prompt_low", "out", "corr", 0.3)

        adjusted = tuner.adjust_temperature("prompt_low", base_temperature=0.5)

        # Should be lower than base
        assert adjusted < 0.5

    def test_adjust_temperature_for_mid_ratings(self, tmp_path):
        """Test adjust_temperature for mid-range ratings."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        tuner.record_feedback("prompt_mid", "out", "corr", 0.4)
        tuner.record_feedback("prompt_mid", "out", "corr", 0.5)

        adjusted = tuner.adjust_temperature("prompt_mid", base_temperature=0.5)

        # Should be slightly lower
        assert adjusted < 0.5

    def test_adjust_temperature_for_high_ratings(self, tmp_path):
        """Test adjust_temperature increases temp for high ratings."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        tuner.record_feedback("prompt_high", "out", "corr", 0.85)
        tuner.record_feedback("prompt_high", "out", "corr", 0.9)

        adjusted = tuner.adjust_temperature("prompt_high", base_temperature=0.5)

        # Should be higher than base
        assert adjusted > 0.5

    def test_get_feedback_summary(self, tmp_path):
        """Test get_feedback_summary returns correct statistics."""
        logger = MagicMock()
        store = FeedbackStore(tmp_path)
        tuner = PromptTuner(store, logger)

        tuner.record_feedback("prompt_1", "out1", "corr1", 0.5)
        tuner.record_feedback("prompt_1", "out2", "corr2", 0.8)
        tuner.record_feedback("prompt_1", "out3", "corr3", 0.9)

        summary = tuner.get_feedback_summary("prompt_1")

        assert summary["total"] == 3
        assert summary["avg_rating"] == pytest.approx(0.733, abs=0.01)
        assert summary["corrections_count"] == 1  # rating < 0.7
        assert summary["good_outputs"] == 2  # rating >= 0.7


# =============================================================================
# DeepLicenseScanner Tests
# =============================================================================


class TestDeepLicenseScanner:
    """Test suite for DeepLicenseScanner."""

    def test_scan_python_deps_parses_requirements(self):
        """Test scan_python_deps parses requirements.txt format."""
        logger = MagicMock()
        scanner = DeepLicenseScanner(logger)

        requirements = """
        flask>=2.0.0
        requests==2.28.1
        pytest
        # Comment line
        numpy>=1.20.0
        """

        deps = scanner.scan_python_deps(requirements)

        assert len(deps) >= 3
        package_names = [d.package_name for d in deps]
        assert "flask" in package_names
        assert "requests" in package_names
        assert "pytest" in package_names

        # Check known licenses are detected
        flask_dep = next(d for d in deps if d.package_name == "flask")
        assert flask_dep.license_id == "BSD-3-Clause"
        assert flask_dep.source == "known"

    def test_scan_node_deps_parses_package_json(self):
        """Test scan_node_deps parses package.json."""
        logger = MagicMock()
        scanner = DeepLicenseScanner(logger)

        package_json = json.dumps(
            {
                "name": "test-project",
                "dependencies": {"express": "^4.18.0", "lodash": "^4.17.21"},
                "devDependencies": {"jest": "^29.0.0"},
            }
        )

        deps = scanner.scan_node_deps(package_json)

        assert len(deps) == 3
        package_names = [d.package_name for d in deps]
        assert "express" in package_names
        assert "lodash" in package_names
        assert "jest" in package_names

        # Check known licenses
        express_dep = next(d for d in deps if d.package_name == "express")
        assert express_dep.license_id == "MIT"

    def test_check_compatibility_detects_mit_compatible(self):
        """Test check_compatibility detects MIT-compatible dependencies."""
        logger = MagicMock()
        scanner = DeepLicenseScanner(logger)

        deps = [
            DependencyLicense("pkg1", "1.0", "MIT", "MIT License", "known"),
            DependencyLicense("pkg2", "2.0", "BSD-3-Clause", "BSD 3-Clause", "known"),
            DependencyLicense("pkg3", "3.0", "Apache-2.0", "Apache 2.0", "known"),
        ]

        report = scanner.check_compatibility("MIT", deps)

        assert report.is_compliant
        assert report.compatible_count == 3
        assert report.incompatible_count == 0

    def test_check_compatibility_detects_gpl_incompatibilities(self):
        """Test check_compatibility detects GPL incompatibilities with Apache."""
        logger = MagicMock()
        scanner = DeepLicenseScanner(logger)

        deps = [
            DependencyLicense("pkg1", "1.0", "GPL-2.0-only", "GPL 2.0", "known"),
            DependencyLicense("pkg2", "2.0", "MIT", "MIT", "known"),
        ]

        report = scanner.check_compatibility("Apache-2.0", deps)

        assert not report.is_compliant
        assert report.incompatible_count == 1
        assert len(report.conflicts) >= 1

        # Check GPL conflict is detected
        gpl_conflict = next(c for c in report.conflicts if c.package_name == "pkg1")
        assert gpl_conflict.severity == "blocking"
        assert "incompatible" in gpl_conflict.reason.lower()

    def test_scan_project_aggregates_multiple_files(self):
        """Test scan_project aggregates dependencies from multiple files."""
        logger = MagicMock()
        scanner = DeepLicenseScanner(logger)

        generated_files = {
            "requirements.txt": "flask>=2.0.0\nrequests==2.28.1",
            "package.json": json.dumps({"dependencies": {"express": "^4.18.0"}}),
            "src/main.py": "# Python source file",
        }

        report = scanner.scan_project(generated_files, project_license="MIT")

        assert report.total_dependencies >= 3
        assert report.project_license == "MIT"

    def test_generate_report_markdown_output_format(self):
        """Test generate_report_markdown produces expected format."""
        logger = MagicMock()
        scanner = DeepLicenseScanner(logger)

        deps = [
            DependencyLicense("flask", "2.0", "BSD-3-Clause", "BSD 3-Clause", "known"),
            DependencyLicense("requests", "2.28", "Apache-2.0", "Apache 2.0", "known"),
        ]

        report = CompatibilityReport(
            project_license="MIT",
            total_dependencies=2,
            compatible_count=2,
            incompatible_count=0,
            unknown_count=0,
            conflicts=[],
            dependencies=deps,
        )

        markdown = scanner.generate_report_markdown(report)

        assert "# License Compliance Report" in markdown
        assert "Project License:** MIT" in markdown
        assert "COMPLIANT" in markdown
        assert "flask" in markdown
        assert "requests" in markdown
        assert "| Package |" in markdown  # Table header

    def test_compatibility_report_is_compliant_property(self):
        """Test CompatibilityReport.is_compliant property."""
        report_compliant = CompatibilityReport(
            project_license="MIT",
            total_dependencies=2,
            compatible_count=2,
            incompatible_count=0,
            unknown_count=0,
            conflicts=[],
            dependencies=[],
        )

        assert report_compliant.is_compliant

        report_non_compliant = CompatibilityReport(
            project_license="Apache-2.0",
            total_dependencies=2,
            compatible_count=1,
            incompatible_count=1,
            unknown_count=0,
            conflicts=[
                LicenseConflict(
                    package_name="gpl_pkg",
                    package_license="GPL-2.0-only",
                    project_license="Apache-2.0",
                    reason="Incompatible",
                )
            ],
            dependencies=[],
        )

        assert not report_non_compliant.is_compliant


# =============================================================================
# UIAnalyzer Tests
# =============================================================================


class TestUIAnalyzer:
    """Test suite for UIAnalyzer."""

    def test_analyze_html_content_detects_missing_alt_text(self):
        """Test analyze_html_content detects missing alt text."""
        logger = MagicMock()
        analyzer = UIAnalyzer(logger)

        html = """
        <html>
        <body>
            <img src="logo.png">
            <img src="banner.jpg">
        </body>
        </html>
        """

        report = asyncio.run(analyzer.analyze_html_content(html))

        assert any(issue.category == "accessibility" and "alt" in issue.description.lower() for issue in report.issues)

    def test_analyze_html_content_detects_missing_form_labels(self):
        """Test analyze_html_content detects missing form labels."""
        logger = MagicMock()
        analyzer = UIAnalyzer(logger)

        html = """
        <html>
        <body>
            <form>
                <input type="text" name="username">
                <input type="password" name="password">
            </form>
        </body>
        </html>
        """

        report = asyncio.run(analyzer.analyze_html_content(html))

        assert any(
            issue.category == "accessibility" and "label" in issue.description.lower() for issue in report.issues
        )

    def test_analyze_html_content_detects_missing_viewport(self):
        """Test analyze_html_content detects missing viewport meta tag."""
        logger = MagicMock()
        analyzer = UIAnalyzer(logger)

        html = """
        <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <h1>Hello</h1>
        </body>
        </html>
        """

        report = asyncio.run(analyzer.analyze_html_content(html))

        assert any(issue.category == "layout" and "viewport" in issue.description.lower() for issue in report.issues)

    def test_calculate_score_scoring_logic(self):
        """Test _calculate_score scoring logic."""
        logger = MagicMock()
        analyzer = UIAnalyzer(logger)

        report = UIAnalysisReport(screenshot_path="test.png")

        # No issues - should be 10.0
        score = analyzer._calculate_score(report)
        assert score == 10.0

        # Add major issue
        report.issues.append(UIIssue("accessibility", "Missing alt", "major", "Add alt text"))
        score = analyzer._calculate_score(report)
        assert score == 8.5  # 10.0 - 1.5

        # Add minor issue
        report.issues.append(UIIssue("layout", "Spacing issue", "minor", "Adjust margins"))
        score = analyzer._calculate_score(report)
        assert score == 8.0  # 8.5 - 0.5

        # Add info issue
        report.issues.append(UIIssue("color", "Color suggestion", "info", "Use darker color"))
        score = analyzer._calculate_score(report)
        assert score == 7.9  # 8.0 - 0.1

    def test_analyze_text_quality_detects_truncation(self):
        """Test _analyze_text_quality detects truncation indicators."""
        logger = MagicMock()
        analyzer = UIAnalyzer(logger)

        report = UIAnalysisReport(screenshot_path="test.png")
        report.extracted_text = "Text truncated... more truncation... and another... yet more..."

        analyzer._analyze_text_quality(report)

        assert any(
            issue.category == "typography" and "truncation" in issue.description.lower() for issue in report.issues
        )

    def test_ui_issue_to_dict_serialization(self):
        """Test UIIssue.to_dict serialization."""
        issue = UIIssue(
            category="accessibility",
            description="Missing alt text",
            severity="major",
            suggestion="Add alt attributes",
            location="top-left",
        )

        result = issue.to_dict()

        assert isinstance(result, dict)
        assert result["category"] == "accessibility"
        assert result["description"] == "Missing alt text"
        assert result["severity"] == "major"
        assert result["suggestion"] == "Add alt attributes"
        assert result["location"] == "top-left"

    def test_ui_analysis_report_to_dict_serialization(self):
        """Test UIAnalysisReport.to_dict serialization."""
        report = UIAnalysisReport(
            screenshot_path="test.png",
            issues=[
                UIIssue("accessibility", "Issue 1", "major", "Fix 1"),
                UIIssue("layout", "Issue 2", "minor", "Fix 2"),
            ],
            overall_score=7.5,
            detected_elements=["button", "form", "header"],
            recommendations=["Improve contrast", "Add labels"],
        )

        result = report.to_dict()

        assert isinstance(result, dict)
        assert result["screenshot_path"] == "test.png"
        assert result["issue_count"] == 2
        assert result["overall_score"] == 7.5
        assert len(result["issues"]) == 2
        assert len(result["detected_elements"]) == 3
        assert len(result["recommendations"]) == 2

    def test_analyze_html_content_no_issues(self):
        """Test analyze_html_content with well-formed HTML."""
        logger = MagicMock()
        analyzer = UIAnalyzer(logger)

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Test Page</title>
        </head>
        <body style="color: black; background: white;">
            <img src="logo.png" alt="Company Logo">
            <form>
                <label for="username">Username:</label>
                <input type="text" id="username" name="username">
            </form>
        </body>
        </html>
        """

        report = asyncio.run(analyzer.analyze_html_content(html))

        # Should have minimal or no issues
        assert report.overall_score >= 8.0
