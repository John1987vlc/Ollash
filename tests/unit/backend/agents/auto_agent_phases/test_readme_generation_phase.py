import pytest
from unittest.mock import MagicMock
from backend.agents.auto_agent_phases.readme_generation_phase import ReadmeGenerationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PhaseContext)
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.project_planner = MagicMock()
    ctx.file_manager = MagicMock()
    return ctx


class TestReadmeGenerationPhase:
    """Test suite for Phase 1: README Generation."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = ReadmeGenerationPhase(mock_context)

        mock_context.project_planner.generate_readme.return_value = "# My Project\nDescription"

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
        mock_context.file_manager.write_file.assert_called_once()
        mock_context.event_publisher.publish.assert_called()
