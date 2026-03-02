"""Unit tests for Opt 4: incremental backlog generation.

Tests cover LogicPlanningPhase._generate_backlog_incrementally().
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_context(model_name: str = "ministral-3:3b", opts: dict | None = None):
    ctx = MagicMock()
    client = MagicMock()
    client.model = model_name
    ctx.llm_manager.get_client.return_value = client
    ctx.config = {"small_model_optimizations": opts if opts is not None else {"opt4_incremental_backlog": True}}
    ctx.decision_blackboard.record_decision.return_value = None
    ctx.logger = MagicMock()
    ctx.generated_projects_dir = Path("/tmp/projects")
    # _is_small_model uses llm_manager internally
    ctx._is_small_model.return_value = True
    ctx._opt_enabled.side_effect = lambda key: True
    return ctx


def _make_task(task_id: str, file_path: str) -> dict:
    return {
        "id": task_id,
        "title": f"Implement {file_path}",
        "file_path": file_path,
        "task_type": "create_file",
        "description": "...",
        "dependencies": [],
    }


def _complete_signal() -> dict:
    return {"complete": True}


@pytest.fixture
def phase():
    ctx = _make_context()
    return LogicPlanningPhase(ctx)


# ---------------------------------------------------------------------------
# Tests: _generate_backlog_incrementally()
# ---------------------------------------------------------------------------


class TestGenerateBacklogIncrementally:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_generates_tasks_until_complete_signal(self, phase):
        """Model produces 2 tasks then signals completion."""
        task1 = _make_task("TASK-001", "utils.py")
        task2 = _make_task("TASK-002", "models.py")
        complete = _complete_signal()

        responses = [
            ({"content": f"<task_json>{json.dumps(task1)}</task_json>"}, {}),
            ({"content": f"<task_json>{json.dumps(task2)}</task_json>"}, {}),
            ({"content": f"<task_json>{json.dumps(complete)}</task_json>"}, {}),
        ]
        phase.context.llm_manager.get_client.return_value.chat.side_effect = responses

        with patch(
            "backend.utils.domains.auto_generation.prompt_templates.AutoGenPrompts.next_backlog_task",
            return_value=("sys", "usr"),
        ):
            backlog = await phase._generate_backlog_incrementally("Test project", "README", {"files": []}, max_tasks=30)

        assert len(backlog) == 2
        assert backlog[0]["id"] == "TASK-001"
        assert backlog[1]["id"] == "TASK-002"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_falls_back_when_no_tasks_produced(self, phase):
        """If no tasks come out, fall back to batch generation."""
        complete = _complete_signal()
        phase.context.llm_manager.get_client.return_value.chat.return_value = (
            {"content": f"<task_json>{json.dumps(complete)}</task_json>"},
            {},
        )
        fallback_backlog = [_make_task("TASK-001", "main.py")]

        with patch(
            "backend.utils.domains.auto_generation.prompt_templates.AutoGenPrompts.next_backlog_task",
            return_value=("sys", "usr"),
        ):
            with patch.object(phase, "_generate_backlog", AsyncMock(return_value=fallback_backlog)):
                backlog = await phase._generate_backlog_incrementally("Test", "README", {}, max_tasks=30)

        assert backlog == fallback_backlog

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_respects_max_tasks_limit(self, phase):
        """Loop stops at max_tasks even if model never signals complete."""
        single_task = _make_task("TASK-001", "utils.py")
        phase.context.llm_manager.get_client.return_value.chat.return_value = (
            {"content": f"<task_json>{json.dumps(single_task)}</task_json>"},
            {},
        )

        with patch(
            "backend.utils.domains.auto_generation.prompt_templates.AutoGenPrompts.next_backlog_task",
            return_value=("sys", "usr"),
        ):
            backlog = await phase._generate_backlog_incrementally("Test", "README", {}, max_tasks=3)

        # Should stop at 3 (max_tasks)
        assert len(backlog) <= 3

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_skips_tasks_without_file_path(self, phase):
        """Tasks missing file_path are skipped."""
        bad_task = {"id": "TASK-001", "title": "No path"}
        good_task = _make_task("TASK-002", "app.py")
        complete = _complete_signal()

        responses = [
            ({"content": f"<task_json>{json.dumps(bad_task)}</task_json>"}, {}),
            ({"content": f"<task_json>{json.dumps(good_task)}</task_json>"}, {}),
            ({"content": f"<task_json>{json.dumps(complete)}</task_json>"}, {}),
        ]
        phase.context.llm_manager.get_client.return_value.chat.side_effect = responses

        with patch(
            "backend.utils.domains.auto_generation.prompt_templates.AutoGenPrompts.next_backlog_task",
            return_value=("sys", "usr"),
        ):
            backlog = await phase._generate_backlog_incrementally("Test", "README", {}, max_tasks=30)

        # Only the task with file_path should be in backlog
        assert len(backlog) == 1
        assert backlog[0]["file_path"] == "app.py"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_records_tasks_to_decision_blackboard(self, phase):
        """Each task is recorded in the decision blackboard."""
        task1 = _make_task("TASK-001", "utils.py")
        complete = _complete_signal()
        responses = [
            ({"content": f"<task_json>{json.dumps(task1)}</task_json>"}, {}),
            ({"content": f"<task_json>{json.dumps(complete)}</task_json>"}, {}),
        ]
        phase.context.llm_manager.get_client.return_value.chat.side_effect = responses

        with patch(
            "backend.utils.domains.auto_generation.prompt_templates.AutoGenPrompts.next_backlog_task",
            return_value=("sys", "usr"),
        ):
            await phase._generate_backlog_incrementally("Test", "README", {}, max_tasks=30)

        phase.context.decision_blackboard.record_decision.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_llm_exception_stops_loop_gracefully(self, phase):
        """If the LLM raises, the loop stops and returns what it has so far."""
        task1 = _make_task("TASK-001", "utils.py")
        responses = [
            ({"content": f"<task_json>{json.dumps(task1)}</task_json>"}, {}),
            RuntimeError("network down"),
        ]

        def side_effect(*args, **kwargs):
            val = responses.pop(0)
            if isinstance(val, Exception):
                raise val
            return val

        phase.context.llm_manager.get_client.return_value.chat.side_effect = side_effect

        with patch(
            "backend.utils.domains.auto_generation.prompt_templates.AutoGenPrompts.next_backlog_task",
            return_value=("sys", "usr"),
        ):
            backlog = await phase._generate_backlog_incrementally("Test", "README", {}, max_tasks=30)

        # Should have the 1 successful task
        assert len(backlog) == 1
