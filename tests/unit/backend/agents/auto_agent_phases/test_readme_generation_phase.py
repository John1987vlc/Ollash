import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agents.auto_agent_phases.readme_generation_phase import ReadmeGenerationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = AsyncMock()
    ctx.event_publisher.subscribe = MagicMock()
    ctx.event_publisher.unsubscribe = MagicMock()
    ctx.project_planner = MagicMock()
    # generate_readme is called with await, so it must be an AsyncMock
    ctx.project_planner.generate_readme = AsyncMock(return_value="# My Project\nDescription")
    ctx.file_manager = MagicMock()
    ctx._is_small_model = MagicMock(return_value=False)
    # LLM mock for Mermaid generation — return content without ```mermaid so README is unchanged
    ctx.llm_manager.get_client.return_value.chat.return_value = (
        {"content": "No mermaid diagrams here"},
        {},
    )
    ctx.initial_exec_params = {}
    ctx.decision_blackboard = MagicMock()
    ctx.documentation_manager = MagicMock()
    ctx.project_type_info = None
    return ctx


class TestReadmeGenerationPhase:
    """Test suite for Phase 1: README Generation."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = ReadmeGenerationPhase(mock_context)

        generated_files = {}
        initial_structure = {}

        result_files, result_struct, file_paths = await phase.execute(
            project_description="A test project",
            project_name="test_proj",
            project_root=tmp_path,
            readme_content="",
            initial_structure=initial_structure,
            generated_files=generated_files,
        )

        assert "README.md" in result_files
        assert result_files["README.md"] == "# My Project\nDescription"
        assert file_paths == ["README.md"]

        mock_context.project_planner.generate_readme.assert_called_once()
        mock_context.event_publisher.publish.assert_called()
