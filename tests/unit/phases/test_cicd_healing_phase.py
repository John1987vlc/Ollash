"""Tests for CICDHealingPhase."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.cicd_healing_phase import CICDHealingPhase


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.cicd_healer = MagicMock()
    ctx.cicd_healer.analyze_failure.return_value = MagicMock(
        category="dependency",
        root_cause="Missing module 'requests'",
        suggested_fixes=["Add 'requests' to requirements.txt"],
        to_dict=lambda: {},
    )
    ctx.cicd_healer.generate_fix = AsyncMock(return_value={})
    return ctx


@pytest.fixture
def phase(mock_context):
    return CICDHealingPhase(context=mock_context)


class TestCICDHealingPhase:
    @pytest.mark.asyncio
    async def test_skips_when_git_push_not_enabled(self, phase):
        files = {"main.py": "print('hello')"}
        result_files, structure, paths = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=Path("/tmp/test"),
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            git_push=False,
            file_paths=[],
        )
        assert result_files == files
        phase.context.logger.info.assert_any_call("CICD Healing: Skipped (git_push not enabled)")

    @pytest.mark.asyncio
    async def test_skips_when_healer_not_available(self, phase):
        phase.context.cicd_healer = None
        files = {"main.py": "print('hello')"}
        result_files, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=Path("/tmp/test"),
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            git_push=True,
            file_paths=[],
        )
        assert result_files == files

    @pytest.mark.asyncio
    async def test_publishes_phase_start_event(self, phase):
        with patch.object(phase, "_wait_for_workflow_completion", new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = None
            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=Path("/tmp/test"),
                readme_content="# Test",
                initial_structure={},
                generated_files={},
                git_push=True,
                file_paths=[],
            )
            phase.context.event_publisher.publish.assert_any_call(
                "phase_start", phase="cicd_healing", message="Monitoring CI/CD pipeline"
            )

    @pytest.mark.asyncio
    async def test_ci_passes_on_first_check(self, phase):
        with patch.object(phase, "_wait_for_workflow_completion", new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = {"conclusion": "success", "name": "CI"}
            result_files, _, _ = await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=Path("/tmp/test"),
                readme_content="# Test",
                initial_structure={},
                generated_files={},
                git_push=True,
                file_paths=[],
            )
            phase.context.logger.info.assert_any_call("CICD Healing: CI passed successfully!")

    @pytest.mark.asyncio
    async def test_healing_attempt_on_failure(self, phase):
        phase.context.cicd_healer.generate_fix = AsyncMock(return_value={"requirements.txt": "requests==2.31.0\n"})

        with (
            patch.object(phase, "_wait_for_workflow_completion", new_callable=AsyncMock) as mock_wait,
            patch.object(phase, "_fetch_workflow_logs") as mock_logs,
            patch.object(phase, "_commit_and_push_fix") as mock_push,
        ):
            # First call: failure, second call: None (break)
            mock_wait.side_effect = [
                {"conclusion": "failure", "databaseId": 123, "name": "CI"},
                None,
            ]
            mock_logs.return_value = "ModuleNotFoundError: No module named 'requests'"

            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=Path("/tmp/test"),
                readme_content="# Test",
                initial_structure={},
                generated_files={"requirements.txt": ""},
                git_push=True,
                file_paths=[],
            )

            phase.context.cicd_healer.analyze_failure.assert_called_once()
            mock_push.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_healing_attempts_respected(self, phase):
        phase.MAX_HEALING_ATTEMPTS = 2
        phase.context.cicd_healer.generate_fix = AsyncMock(return_value={})

        with (
            patch.object(phase, "_wait_for_workflow_completion", new_callable=AsyncMock) as mock_wait,
            patch.object(phase, "_fetch_workflow_logs") as mock_logs,
        ):
            mock_wait.return_value = {
                "conclusion": "failure",
                "databaseId": 1,
                "name": "CI",
            }
            mock_logs.return_value = "error"

            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=Path("/tmp/test"),
                readme_content="# Test",
                initial_structure={},
                generated_files={},
                git_push=True,
                file_paths=[],
            )

            # Should stop after generate_fix returns empty
            assert phase.context.cicd_healer.analyze_failure.call_count <= 2

    def test_fetch_workflow_logs_success(self, phase):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Log output here")
            result = phase._fetch_workflow_logs(Path("/tmp"), 123)
            assert result == "Log output here"

    def test_fetch_workflow_logs_failure(self, phase):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = phase._fetch_workflow_logs(Path("/tmp"), 123)
            assert result == ""

    def test_commit_and_push_fix(self, phase):
        with patch("backend.agents.auto_agent_phases.cicd_healing_phase.GitManager") as MockGit:
            mock_git = MagicMock()
            MockGit.return_value = mock_git
            phase._commit_and_push_fix(Path("/tmp"), 1, "Missing dependency")
            mock_git.add.assert_called_once()
            mock_git.commit.assert_called_once()
            mock_git.push.assert_called_once()
