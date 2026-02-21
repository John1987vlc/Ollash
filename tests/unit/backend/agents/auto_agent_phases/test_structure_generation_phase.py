import pytest
from unittest.mock import MagicMock, patch
from backend.agents.auto_agent_phases.structure_generation_phase import StructureGenerationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PhaseContext)
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.structure_generator = MagicMock()
    ctx.file_manager = MagicMock()
    return ctx


class TestStructureGenerationPhase:
    """Test suite for Phase 2: Structure Generation."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = StructureGenerationPhase(mock_context)

        mock_structure = {"folders": ["src", "tests"], "files": ["src/main.py", "tests/test_main.py"]}
        mock_context.structure_generator.generate.return_value = mock_structure

        from backend.utils.domains.auto_generation.structure_generator import StructureGenerator

        with patch.object(StructureGenerator, "extract_file_paths", return_value=["src/main.py", "tests/test_main.py"]):
            result_files, result_struct, file_paths = await phase.execute(
                project_description="desc",
                project_name="name",
                project_root=tmp_path,
                readme_content="# Readme",
                initial_structure={},
                generated_files={},
            )

            assert "project_structure.json" in result_files
            assert result_struct == mock_structure
            assert len(file_paths) == 2

            mock_context.structure_generator.generate.assert_called_once()
            mock_context.file_manager.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_fallback(self, mock_context, tmp_path):
        phase = StructureGenerationPhase(mock_context)
        mock_context.structure_generator.generate.return_value = None

        from backend.utils.domains.auto_generation.structure_generator import StructureGenerator

        with patch.object(StructureGenerator, "create_fallback_structure") as mock_fallback:
            with patch.object(StructureGenerator, "extract_file_paths", return_value=["fallback.py"]):
                mock_fallback.return_value = {"files": ["fallback.py"]}

                result_files, result_struct, file_paths = await phase.execute(
                    project_description="desc",
                    project_name="name",
                    project_root=tmp_path,
                    readme_content="# Readme",
                    initial_structure={},
                    generated_files={},
                )

                assert mock_fallback.called
                assert file_paths == ["fallback.py"]
