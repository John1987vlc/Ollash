"""Tests for SeniorReviewPhase PR-based review enhancement."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.senior_review_phase import SeniorReviewPhase


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.config = {"senior_review_max_attempts": 1}
    ctx.senior_reviewer = MagicMock()
    ctx.senior_reviewer.perform_review.return_value = {
        "status": "passed",
        "summary": "All checks passed.",
        "issues": [],
    }
    ctx.contingency_planner = MagicMock()
    ctx.file_completeness_checker = MagicMock()
    ctx.file_completeness_checker.verify_and_fix.return_value = {}
    ctx.file_refiner = MagicMock()
    ctx.error_knowledge_base = MagicMock()
    ctx.error_knowledge_base.get_error_statistics.return_value = {}
    ctx.fragment_cache = MagicMock()
    ctx.fragment_cache.stats.return_value = {}
    return ctx


@pytest.fixture
def phase(mock_context):
    return SeniorReviewPhase(context=mock_context)


class TestSeniorReviewPR:
    @pytest.mark.asyncio
    async def test_pr_not_created_when_flag_disabled(self, phase, tmp_path):
        files = {"main.py": "print('hello')"}
        with patch.object(phase, "_create_review_pr") as mock_pr:
            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=tmp_path,
                readme_content="# Test",
                initial_structure={},
                generated_files=files,
                file_paths=[],
                senior_review_as_pr=False,
                git_token="ghp_test",
            )
            mock_pr.assert_not_called()

    @pytest.mark.asyncio
    async def test_pr_not_created_without_token(self, phase, tmp_path):
        files = {"main.py": "print('hello')"}
        with patch.object(phase, "_create_review_pr") as mock_pr:
            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=tmp_path,
                readme_content="# Test",
                initial_structure={},
                generated_files=files,
                file_paths=[],
                senior_review_as_pr=True,
                git_token="",
            )
            mock_pr.assert_not_called()

    @pytest.mark.asyncio
    async def test_pr_created_when_enabled(self, phase, tmp_path):
        files = {"main.py": "print('hello')"}
        with patch.object(phase, "_create_review_pr") as mock_pr:
            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=tmp_path,
                readme_content="# Test",
                initial_structure={},
                generated_files=files,
                file_paths=[],
                senior_review_as_pr=True,
                git_token="ghp_test",
            )
            mock_pr.assert_called_once()

    def test_format_pr_body_passed(self, phase):
        review = {"status": "passed", "summary": "All good", "issues": []}
        body = phase._format_pr_body(review, {"main.py": ""}, Path("/tmp"))
        assert "PASSED" in body
        assert "95/100" in body
        assert "All good" in body

    def test_format_pr_body_with_issues(self, phase):
        review = {
            "status": "failed",
            "summary": "Issues found",
            "issues": [
                {
                    "severity": "high",
                    "file": "main.py",
                    "description": "Missing error handling",
                    "recommendation": "Add try/except",
                },
                {
                    "severity": "low",
                    "file": "utils.py",
                    "description": "Unused import",
                    "recommendation": "Remove import",
                },
            ],
        }
        body = phase._format_pr_body(review, {"main.py": "", "utils.py": ""}, Path("/tmp"))
        assert "Issues" in body
        assert "main.py" in body
        assert "high" in body

    def test_format_pr_body_coherence_scores(self, phase):
        # 0 issues -> 95
        body = phase._format_pr_body(
            {"status": "passed", "summary": "", "issues": []}, {}, Path("/tmp")
        )
        assert "95/100" in body

        # 3 issues -> 75
        issues_3 = [{"severity": "low", "file": "a.py", "description": "x"}] * 3
        body = phase._format_pr_body(
            {"status": "failed", "summary": "", "issues": issues_3}, {}, Path("/tmp")
        )
        assert "75/100" in body

        # 8 issues -> 55
        issues_8 = [{"severity": "low", "file": "a.py", "description": "x"}] * 8
        body = phase._format_pr_body(
            {"status": "failed", "summary": "", "issues": issues_8}, {}, Path("/tmp")
        )
        assert "55/100" in body

        # 15 issues -> 35
        issues_15 = [{"severity": "low", "file": "a.py", "description": "x"}] * 15
        body = phase._format_pr_body(
            {"status": "failed", "summary": "", "issues": issues_15}, {}, Path("/tmp")
        )
        assert "35/100" in body

    def test_run_ruff_metrics_success(self, phase):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="E501: 5 occurrences\nW291: 2 occurrences"
            )
            result = phase._run_ruff_metrics(Path("/tmp"))
            assert "E501" in result

    def test_run_ruff_metrics_failure(self, phase):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = phase._run_ruff_metrics(Path("/tmp"))
            assert result == ""

    def test_post_review_comments(self, phase):
        issues = [
            {
                "severity": "high",
                "file": "main.py",
                "description": "SQL injection risk",
                "recommendation": "Use parameterized queries",
            },
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            phase._post_review_comments(Path("/tmp"), 42, issues)
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "42" in call_args
            assert "gh" in call_args

    def test_post_review_comments_limits_to_10(self, phase):
        issues = [
            {"severity": "low", "file": f"file{i}.py", "description": "issue", "recommendation": "fix"}
            for i in range(15)
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            phase._post_review_comments(Path("/tmp"), 1, issues)
            assert mock_run.call_count == 10
