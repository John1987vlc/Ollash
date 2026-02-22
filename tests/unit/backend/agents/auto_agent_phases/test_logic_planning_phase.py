import pytest
import json
from unittest.mock import MagicMock
from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PhaseContext)
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.llm_manager = MagicMock()
    ctx.file_manager = MagicMock()
    return ctx


class TestLogicPlanningPhase:
    """Test suite for Phase 2.5: Logic Planning."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = LogicPlanningPhase(mock_context)

        # Mock LLM response for a category
        mock_planner = MagicMock()
        mock_planner.chat.return_value = (
            {"content": '{"src/main.py": {"purpose": "main entry", "exports": ["main"]}}'},
            {"usage": {}},
        )
        mock_context.llm_manager.get_client.return_value = mock_planner

        generated_files = {}
        initial_structure = {"files": ["src/main.py"]}
        file_paths = ["src/main.py"]

        result_files, result_struct, result_paths = await phase.execute(
            project_description="desc",
            project_name="name",
            project_root=tmp_path,
            readme_content="# Readme",
            initial_structure=initial_structure,
            generated_files=generated_files,
            file_paths=file_paths,
        )

        assert "IMPLEMENTATION_PLAN.json" in result_files
        plan = json.loads(result_files["IMPLEMENTATION_PLAN.json"])
        assert "src/main.py" in plan
        assert plan["src/main.py"]["purpose"] == "main entry"

        # Verify it was stored in context
        assert mock_context.logic_plan == plan
        # Now we write IMPLEMENTATION_PLAN.json and BACKLOG.json
        assert mock_context.file_manager.write_file.call_count == 2

    def test_categorize_files(self, mock_context):
        phase = LogicPlanningPhase(mock_context)
        files = ["src/main.py", "tests/test_app.py", "config/settings.json", "utils/helper.py"]

        categories = phase._categorize_files(files)

        assert "main" in categories
        assert "tests" in categories
        assert "config" in categories
        assert "utils" in categories
        assert "src/main.py" in categories["main"]

    @pytest.mark.asyncio
    async def test_plan_category_fallback(self, mock_context):
        phase = LogicPlanningPhase(mock_context)

        # Simulate LLM failure
        mock_planner = MagicMock()
        mock_planner.chat.side_effect = Exception("LLM Down")
        mock_context.llm_manager.get_client.return_value = mock_planner

        files = ["unknown.py"]
        plan = await phase._plan_category("other", files, "desc", "readme", {})

        # Should use basic plan fallback
        assert "unknown.py" in plan
        assert "purpose" in plan["unknown.py"]
        assert "Implementation of other logic for: desc..." in plan["unknown.py"]["purpose"]
