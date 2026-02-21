import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PhaseContext)
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.dependency_graph = MagicMock()
    ctx.parallel_generator = MagicMock()
    ctx.error_knowledge_base = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.llm_manager = MagicMock()
    ctx.response_parser = MagicMock()
    ctx.file_content_generator = MagicMock()
    return ctx


class TestFileContentGenerationPhase:
    """Test suite for Phase 4: File Content Generation."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = FileContentGenerationPhase(mock_context)

        mock_context.dependency_graph.get_generation_order.return_value = ["main.py"]
        mock_context.dependency_graph.get_context_for_file.return_value = {}
        mock_context.logic_plan = {"main.py": {"exports": ["main"]}}

        async def mock_generate_files(tasks, gen_fn, **kwargs):
            for task in tasks:
                await gen_fn(task.file_path, task.context)
            return []

        mock_context.parallel_generator.generate_files.side_effect = mock_generate_files
        mock_context.parallel_generator.get_statistics.return_value = {
            "success": 1,
            "total": 1,
            "avg_time_per_file": 1.0,
        }

        with patch.object(phase, "_generate_with_plan", new=AsyncMock()) as mock_gen_plan:
            # Provide enough content to pass the 50 char strip check
            mock_gen_plan.return_value = "def main():\n    print('hello world')\n" + "#" * 60

            generated_files = {}
            result_files, result_struct, result_paths = await phase.execute(
                project_description="desc",
                project_name="name",
                project_root=tmp_path,
                readme_content="# Readme",
                initial_structure={},
                generated_files=generated_files,
                file_paths=["main.py"],
            )

            assert "main.py" in result_files
            assert "def main()" in result_files["main.py"]
            mock_context.file_manager.write_file.assert_called_once()

    def test_validate_file_content(self, mock_context):
        phase = FileContentGenerationPhase(mock_context)
        plan = {"exports": ["calculate"]}

        # Valid content (long enough and contains export)
        valid_content = "def calculate():\n    return 42\n" + "#" * 60
        assert phase._validate_file_content("test.py", valid_content, plan) is True

        # Missing export
        invalid_export = "def wrong():\n    pass\n" + "#" * 60
        assert phase._validate_file_content("test.py", invalid_export, plan) is False

        # Content too short (strip removes trailing spaces)
        short_content = "def calculate():\n    pass" + " " * 100
        assert phase._validate_file_content("test.py", short_content, plan) is False

    def test_infer_language(self, mock_context):
        phase = FileContentGenerationPhase(mock_context)
        assert phase._infer_language("main.py") == "python"
        assert phase._infer_language("app.js") == "javascript"
        assert phase._infer_language("main.go") == "go"
        assert phase._infer_language("unknown.xyz") == "unknown"
