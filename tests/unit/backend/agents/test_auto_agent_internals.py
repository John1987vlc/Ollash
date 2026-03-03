import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from backend.agents.auto_agent import AutoAgent


@pytest.fixture
def mock_deps():
    return {
        "phase_context": MagicMock(),
        "phases": [],
        "project_analysis_phase_factory": MagicMock(),
        "kernel": MagicMock(),
        "llm_manager": MagicMock(),
        "llm_recorder": MagicMock(),
        "dependency_scanner": MagicMock(),
    }


@pytest.fixture
def agent(mock_deps):
    mock_deps["kernel"].get_full_config.return_value = {"models": {"writer": "qwen"}}
    mock_deps["phase_context"].generated_projects_dir = Path("/tmp/projects")
    return AutoAgent(**mock_deps)


def test_manage_github_issues_basic(agent):
    agent.git_tool = MagicMock()
    agent.git_tool.create_issue.return_value = {"success": True, "number": 123}

    structure = {
        "tasks": [
            {"id": "T1", "title": "Task 1", "description": "Desc 1"},
            {"id": "T2", "title": "Task 2", "description": "Desc 2", "dependencies": ["T1"]},
        ]
    }
    agent.phase_context.backlog = []  # Use structure

    agent._manage_github_issues(structure)

    assert agent.git_tool.create_issue.call_count == 2
    # Verify linking call (second pass)
    agent.git_tool.update_issue_body.assert_called_with(123, "Desc 2\n\n🚫 Blocked by: #123")


@pytest.mark.asyncio
async def test_update_ollash_manifest(agent):
    mock_writer = MagicMock()
    mock_writer.chat.return_value = ({"content": "# Manifest content"}, {})
    agent.llm_manager.get_client.return_value = mock_writer

    agent.phase_context.backlog = [{"status": "done", "github_number": 1}]
    agent.phase_context.initial_exec_params = {"project_name": "test", "project_description": "desc"}
    agent.phase_context.current_version = "v0.1.0"

    mock_prompts = {
        "generate_manifest": {
            "system": "You are a manifest writer.",
            "user": (
                "Project: {project_name}, Desc: {project_description}, "
                "Backlog: {backlog_summary}, Task: {current_task}, "
                "Version: {current_version}, Next: {next_tag}, Decisions: {last_decisions}"
            ),
        }
    }

    with patch("backend.utils.core.llm.prompt_loader.PromptLoader") as mock_loader_cls:
        mock_loader_cls.return_value.load_prompt = AsyncMock(return_value=mock_prompts)
        content = await agent._update_ollash_manifest("T1")

    assert content == "# Manifest content"
    agent.llm_manager.get_client.assert_called_with("writer")


def test_finalize_project(agent):
    execution_plan = MagicMock()
    project_root = Path("/tmp/project")
    agent.event_publisher = MagicMock()
    agent.phase_context.fragment_cache.stats = AsyncMock(return_value={})

    agent._finalize_project("test", project_root, 5, execution_plan)

    execution_plan.mark_complete.assert_called_once()
    agent.phase_context.file_manager.write_file.assert_called()
    assert agent.event_publisher.publish.call_count >= 2


# ---------------------------------------------------------------------------
# Tests: _build_adaptive_phases()
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildAdaptivePhases:
    """_build_adaptive_phases() returns the correct phase list per model tier."""

    def _make_typed_mock(self, cls):
        """Return a MagicMock that passes isinstance(mock, cls)."""
        return MagicMock(spec=cls)

    def test_full_tier_all_phases_returned(self, agent):
        from backend.agents.auto_agent_phases.exhaustive_review_repair_phase import ExhaustiveReviewRepairPhase
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase
        from backend.agents.auto_agent_phases.cicd_healing_phase import CICDHealingPhase
        from backend.agents.auto_agent_phases.license_compliance_phase import LicenseCompliancePhase

        p1 = self._make_typed_mock(ExhaustiveReviewRepairPhase)
        p2 = self._make_typed_mock(DynamicDocumentationPhase)
        p3 = self._make_typed_mock(CICDHealingPhase)
        p4 = self._make_typed_mock(LicenseCompliancePhase)
        p5 = MagicMock()

        agent.phases = [p1, p2, p3, p4, p5]
        agent.phase_context._is_small_model.return_value = False
        agent.phase_context._is_mid_model.return_value = False

        result = agent._build_adaptive_phases()
        assert len(result) == 5

    def test_nano_tier_skips_4_heavy_phases(self, agent):
        from backend.agents.auto_agent_phases.exhaustive_review_repair_phase import ExhaustiveReviewRepairPhase
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase
        from backend.agents.auto_agent_phases.cicd_healing_phase import CICDHealingPhase
        from backend.agents.auto_agent_phases.license_compliance_phase import LicenseCompliancePhase

        p1 = self._make_typed_mock(ExhaustiveReviewRepairPhase)
        p2 = self._make_typed_mock(DynamicDocumentationPhase)
        p3 = self._make_typed_mock(CICDHealingPhase)
        p4 = self._make_typed_mock(LicenseCompliancePhase)
        p5 = MagicMock()

        agent.phases = [p1, p2, p3, p4, p5]
        agent.phase_context._is_small_model.return_value = True
        agent.phase_context._is_mid_model.return_value = False

        result = agent._build_adaptive_phases()
        # Only p5 (untyped generic) survives
        assert len(result) == 1
        assert result[0] is p5

    def test_slim_tier_skips_2_doc_ci_phases(self, agent):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase
        from backend.agents.auto_agent_phases.cicd_healing_phase import CICDHealingPhase

        p1 = self._make_typed_mock(DynamicDocumentationPhase)
        p2 = self._make_typed_mock(CICDHealingPhase)
        p3 = MagicMock()
        p4 = MagicMock()
        p5 = MagicMock()

        agent.phases = [p1, p2, p3, p4, p5]
        agent.phase_context._is_small_model.return_value = False
        agent.phase_context._is_mid_model.return_value = True

        result = agent._build_adaptive_phases()
        # p1 and p2 are skipped; p3, p4, p5 survive
        assert len(result) == 3

    def test_exception_returns_all_phases(self, agent):
        agent.phases = [MagicMock(), MagicMock()]
        agent.phase_context._is_small_model.side_effect = RuntimeError("oops")

        result = agent._build_adaptive_phases()
        assert len(result) == 2
