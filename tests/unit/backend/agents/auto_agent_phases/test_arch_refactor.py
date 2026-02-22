import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase
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
    
    # Mocks for ProjectAnalysisPhase/LogicPlanningPhase
    ctx.group_files_by_language = MagicMock(return_value={"python": ["main.py"]})
    ctx.infer_language = MagicMock(return_value="python")
    return ctx

class TestArchRefactor:
    """Test suite for the Architectural Refactor of AutoAgent Phases."""

    def test_binary_guard(self, mock_context):
        """Verify that Binary Guard correctly identifies binary files."""
        phase = FileContentGenerationPhase(mock_context)
        
        assert phase._is_binary_file("image.png") is True
        assert phase._is_binary_file("audio.mp3") is True
        assert phase._is_binary_file("font.ttf") is True
        assert phase._is_binary_file("archive.zip") is True
        assert phase._is_binary_file("script.py") is False
        assert phase._is_binary_file("styles.css") is False

    def test_strict_validation_hallucination(self, mock_context):
        """Verify that hallucination detection catches typical LLM filler phrases."""
        phase = FileContentGenerationPhase(mock_context)
        plan = {"exports": ["main"]}
        
        # Hallucination at start
        hallucinated_content = """Sure, I can help with that. Here is the code:
def main():
    pass"""
        assert phase._validate_file_content("main.py", hallucinated_content, plan) is False
        
        # Safe if in comments
        safe_content = """# Here is the code for the main function
def main():
    return 0""" + "#" * 50
        assert phase._validate_file_content("main.py", safe_content, plan) is True

    def test_strict_validation_min_payload(self, mock_context):
        """Verify min payload check for main files."""
        phase = FileContentGenerationPhase(mock_context)
        plan = {"exports": ["app"]}
        
        # Main file with tiny payload
        tiny_main = "app = 1"
        assert phase._validate_file_content("app.py", tiny_main, plan) is False
        
        # Main file with sufficient payload
        good_main = """app = Flask(__name__)
@app.route('/')
def index(): return 'hi'""" + "#" * 100
        assert phase._validate_file_content("app.py", good_main, plan) is True

    def test_logic_planning_fallback_intent(self, mock_context):
        """Verify that fallback planning preserves project description intent."""
        phase = LogicPlanningPhase(mock_context)
        project_desc = "Create a high-performance trading bot for crypto"
        
        plans = phase._create_basic_plans(["bot.py"], "main", project_desc)
        
        assert "bot.py" in plans
        assert "trading bot" in plans["bot.py"]["purpose"]
        assert "trading bot" in plans["bot.py"]["main_logic"][0]
        assert project_desc in plans["bot.py"]["main_logic"][0]

    @pytest.mark.asyncio
    async def test_file_gen_skips_binary(self, mock_context, tmp_path):
        """Test that Phase 4 actually skips binary files during execution."""
        phase = FileContentGenerationPhase(mock_context)
        
        # Binary guard is now at the start of the loop
        mock_context.backlog = [
            {"id": "T1", "title": "Logo", "file_path": "logo.png", "task_type": "create_file"},
            {"id": "T2", "title": "Main", "file_path": "main.py", "task_type": "create_file"}
        ]
        
        # Mock LLM for the non-binary file
        mock_client = MagicMock()
        mock_client.chat.return_value = (
            {"content": "<thinking_process>Análisis</thinking_process><code_created>print('ok')</code_created>"}, 
            {"prompt_tokens": 10, "completion_tokens": 10}
        )
        mock_context.llm_manager.get_client.return_value = mock_client
        
        # Mock Validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(status=MagicMock(name="VALID"))
        mock_context.files_ctx.validator = mock_validator

        generated_files = {}
        await phase.execute(
            project_description="desc",
            project_name="name",
            project_root=tmp_path,
            readme_content="# Readme",
            initial_structure={},
            generated_files=generated_files,
            file_paths=["logo.png", "main.py"]
        )
        
        # logo.png should be in generated_files as empty string (skipped)
        assert "logo.png" in generated_files
        assert generated_files["logo.png"] == ""
        
        # main.py should be generated
        assert "main.py" in generated_files
        assert "print('ok')" in generated_files["main.py"]
