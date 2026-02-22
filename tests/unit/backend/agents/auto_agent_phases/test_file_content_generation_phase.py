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
    
    # Files sub-context
    ctx.files_ctx = MagicMock()
    ctx.files_ctx.validator = MagicMock()
    ctx.files_ctx.validator.validate.return_value = MagicMock(status=MagicMock(name="VALID"))
    
    return ctx


class TestFileContentGenerationPhase:
    """Test suite for Phase 4: File Content Generation."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = FileContentGenerationPhase(mock_context)

        # Setup Mock Backlog
        mock_context.backlog = [
            {"id": "T1", "title": "Task 1", "file_path": "main.py", "task_type": "create_file"}
        ]
        mock_context.select_related_files.return_value = {}
        
        # Mock LLM Client
        mock_client = MagicMock()
        mock_client.chat.return_value = (
            {"content": "<pensamiento>Análisis</pensamiento><codigo>def main(): pass</codigo>"}, 
            {"prompt_tokens": 10, "completion_tokens": 10}
        )
        mock_context.llm_manager.get_client.return_value = mock_client
        
        # Mock Validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(status=MagicMock(name="VALID"))
        mock_context.files_ctx.validator = mock_validator

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
        assert "def main(): pass" in result_files["main.py"]
        mock_context.file_manager.write_file.assert_called()

    def test_validate_file_content(self, mock_context):
        phase = FileContentGenerationPhase(mock_context)
        plan = {"exports": ["calculate"]}

        # Valid content (long enough and contains export)
        valid_content = "def calculate():\n    return 42\n" + "#" * 60
        assert phase._validate_file_content("test.py", valid_content, plan) is True

        # Missing export
        invalid_export = "def wrong():\n    pass\n" + "#" * 60
        assert phase._validate_file_content("test.py", invalid_export, plan) is False

        # Content too short for main file (threshold is 20)
        short_main_content = "def main(): pass" # 16 chars
        assert phase._validate_file_content("main.py", short_main_content, plan) is False
        
        # Valid main content
        good_main_content = "def main():\n    print('Hello World')\n" + "#" * 20
        assert phase._validate_file_content("main.py", good_main_content, plan) is True

    def test_infer_language(self, mock_context):
        phase = FileContentGenerationPhase(mock_context)
        assert phase._infer_language("main.py") == "python"
        assert phase._infer_language("app.js") == "javascript"
        assert phase._infer_language("main.go") == "go"
        assert phase._infer_language("unknown.xyz") == "unknown"
