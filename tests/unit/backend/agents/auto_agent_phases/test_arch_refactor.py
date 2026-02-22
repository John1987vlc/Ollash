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
        
        mock_context.dependency_graph.get_generation_order.return_value = ["logo.png", "main.py"]
        mock_context.dependency_graph.get_context_for_file.return_value = {}
        mock_context.logic_plan = {"main.py": {"exports": ["main"]}}
        
        generated_files = {}
        # We don't need to mock parallel_generator if we are just testing the skip logic in the task loop
        # But execute() calls generate_files, so we mock it to avoid real generation
        mock_context.parallel_generator.generate_files = AsyncMock(return_value={})
        mock_context.parallel_generator.get_statistics.return_value = {"success": 1, "total": 2, "avg_time_per_file": 0}

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
        # The parallel generator should only have been called for main.py
        args, _ = mock_context.parallel_generator.generate_files.call_args
        tasks = args[0]
        assert len(tasks) == 1
        assert tasks[0].file_path == "main.py"
