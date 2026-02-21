"""Tests for LogicPlanningPhase."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.llm_manager = MagicMock()

    # Mock LLM Client
    mock_llm_client = MagicMock()
    mock_llm_client.chat.return_value = (
        {"content": json.dumps({
            "src/main.py": {
                "purpose": "Main entry point",
                "exports": ["main"],
                "imports": ["os"],
                "main_logic": ["Initialize app", "Run loop"],
                "validation": ["Check exit code"]
            }
        })},
        {"total_tokens": 100}
    )
    ctx.llm_manager.get_client.return_value = mock_llm_client

    return ctx


@pytest.fixture
def phase(mock_context):
    return LogicPlanningPhase(context=mock_context)


class TestLogicPlanningPhase:
    @pytest.mark.asyncio
    async def test_execute_creates_plan(self, phase):
        file_paths = ["src/main.py", "src/utils.py"]
        project_root = Path("/tmp/test_project")

        result_files, structure, paths = await phase.execute(
            project_description="A test project",
            project_name="test_project",
            project_root=project_root,
            readme_content="# Test Project",
            initial_structure={},
            generated_files={},
            file_paths=file_paths
        )

        # Verify result structures
        assert "IMPLEMENTATION_PLAN.json" in result_files
        assert phase.context.logic_plan is not None

        # Verify file manager was called to save the plan
        phase.context.file_manager.write_file.assert_called()

        # Verify event publishing
        phase.context.event_publisher.publish.assert_any_call(
            "phase_start", phase="2.5", message="Creating logic implementation plans"
        )
        phase.context.event_publisher.publish.assert_any_call(
            "phase_complete", phase="2.5", message="Logic plan created for 1 files"
        )

    def test_categorize_files(self, phase):
        files = [
            "config.json", "src/main.py", "utils/helper.py",
            "tests/test_main.py", "README.md", "static/style.css", "other.txt"
        ]
        categories = phase._categorize_files(files)

        assert "config" in categories
        assert "main" in categories
        assert "utils" in categories
        assert "tests" in categories
        assert "docs" in categories
        assert "web" in categories
        assert "other" in categories

        assert "config.json" in categories["config"]
        assert "src/main.py" in categories["main"]

    @pytest.mark.asyncio
    async def test_plan_category_fallback_on_llm_error(self, phase):
        phase.context.llm_manager.get_client().chat.side_effect = Exception("LLM Error")

        # This should trigger fallback to basic plans
        plans = await phase._plan_category(
            "main", ["src/main.py"], "desc", "# Readme", {}
        )

        assert "src/main.py" in plans
        assert plans["src/main.py"]["purpose"] == "Main application entry point"

    def test_create_basic_plans(self, phase):
        files = ["src/app.js"]
        plans = phase._create_basic_plans(files, "web")

        assert "src/app.js" in plans
        assert "JavaScript" in plans["src/app.js"]["purpose"]
