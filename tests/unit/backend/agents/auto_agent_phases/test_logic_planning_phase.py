import pytest
import json
from unittest.mock import MagicMock, patch
from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PhaseContext)
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = MagicMock()
    ctx.event_publisher.publish_sync = MagicMock()
    ctx.llm_manager = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.response_parser = MagicMock()
    # Mock some context attributes
    ctx._is_small_model.return_value = False
    ctx._opt_enabled.return_value = False
    return ctx


class TestLogicPlanningPhase:
    """Test suite for Phase 2.5: Logic Planning."""

    def test_execute_success(self, mock_context, tmp_path):
        phase = LogicPlanningPhase(mock_context)

        # Mock AutoGenPrompts
        with patch("backend.agents.auto_agent_phases.logic_planning_phase.AutoGenPrompts") as mock_prompts:
            mock_prompts.logic_planning.return_value = ("system", "user")

            # Mock LLM response
            mock_planner = MagicMock()
            # The real phase uses LogicPlanningOutput pydantic model, so we need a valid structure
            valid_response = {
                "logic_plan": {
                    "src/main.py": {
                        "purpose": "main entry",
                        "exports": ["main"],
                        "imports": [],
                        "main_logic": ["step 1"],
                        "validation": ["check 1"],
                        "dependencies": [],
                    }
                },
                "backlog": [
                    {
                        "id": "TASK-001",
                        "title": "Implement main",
                        "description": "main",
                        "file_path": "src/main.py",
                        "task_type": "create_file",
                        "dependencies": [],
                        "context_files": [],
                    }
                ],
            }

            mock_planner.chat.return_value = (
                {"content": json.dumps(valid_response)},
                {"usage": {}},
            )
            mock_context.llm_manager.get_client.return_value = mock_planner
            mock_context.response_parser.extract_json.return_value = valid_response

            generated_files = {}
            initial_structure = {"files": ["src/main.py"]}
            file_paths = ["src/main.py"]

            # Fix: execute is actually run in the current LogicPlanningPhase implementation
            # Checking logic_planning_phase.py again... it uses async def run
            result_files, result_struct, result_paths = phase.run(
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
            # Now we write IMPLEMENTATION_PLAN.json, BACKLOG.json, and tasks.json (F6)
            assert mock_context.file_manager.write_file.call_count == 3

    def test_categorize_files(self, mock_context):
        phase = LogicPlanningPhase(mock_context)
        files = ["src/main.py", "tests/test_app.py", "config/settings.json", "utils/helper.py"]

        categories = phase._categorize_files(files)

        assert "main" in categories
        assert "tests" in categories
        assert "config" in categories
        assert "utils" in categories
        assert "src/main.py" in categories["main"]

    def test_plan_category_fallback(self, mock_context):
        phase = LogicPlanningPhase(mock_context)

        with patch("backend.agents.auto_agent_phases.logic_planning_phase.AutoGenPrompts") as mock_prompts:
            mock_prompts.architecture_planning_detailed.return_value = ("system", "user")

            # Mock LLM response
            mock_planner = MagicMock()
            valid_cat_plan = {"unknown.py": {"purpose": "Implementation of other logic for: desc...", "exports": []}}
            mock_planner.chat.return_value = (
                {"content": json.dumps(valid_cat_plan)},
                {"usage": {}},
            )
            mock_context.llm_manager.get_client.return_value = mock_planner

            # LogicPlanningPhase uses LLMResponseParser.extract_json inside _plan_category too
            # but wait, logic_planning_phase.py has a local import or uses self.context.response_parser?
            # Looking at logic_planning_phase.py:
            # return LLMResponseParser.extract_json(response_data.get("content", "")) or {}

            with patch("backend.utils.core.llm.llm_response_parser.LLMResponseParser.extract_json") as mock_extract:
                mock_extract.return_value = valid_cat_plan

                files = ["unknown.py"]
                plan = phase._plan_category("other", files, "desc", "readme", {}, {})

                # Should use basic plan fallback or LLM result
                assert "unknown.py" in plan
                assert "purpose" in plan["unknown.py"]
                assert "Implementation of other logic for: desc..." in plan["unknown.py"]["purpose"]
