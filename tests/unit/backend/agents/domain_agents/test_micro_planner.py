"""Unit tests for the Micro-Planner in DeveloperAgent (Mejora 1).

Tests cover _decompose_micro_steps: success, failure, caps, padding.
All LLM calls are mocked — no network I/O.
"""

import json
import pytest
from unittest.mock import MagicMock

from backend.agents.domain_agents.developer_agent import DeveloperAgent


def _make_ep():
    ep = MagicMock()
    ep.publish_sync = MagicMock()
    return ep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_developer_agent(llm_response: str = "", raise_exc: bool = False) -> DeveloperAgent:
    """Build a minimal DeveloperAgent with mocked dependencies."""
    mock_client = MagicMock()
    if raise_exc:
        mock_client.chat.side_effect = RuntimeError("LLM unavailable")
    else:
        mock_client.chat.return_value = (
            {"message": {"content": llm_response}},
            None,
        )

    agent = DeveloperAgent(
        file_content_generator=MagicMock(),
        code_patcher=MagicMock(),
        locked_file_manager=MagicMock(),
        parallel_file_generator=MagicMock(),
        event_publisher=_make_ep(),
        logger=MagicMock(),
        tool_dispatcher=MagicMock(),
        instance_id=0,
        llm_client=mock_client,
    )
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecomposeMicroSteps:
    def test_success_returns_step_list(self):
        raw = json.dumps(["Define imports", "Define Config class", "Implement load()"])
        agent = _make_developer_agent(llm_response=raw)
        steps = agent._decompose_micro_steps("src/config.py", {"purpose": "Load config"})
        assert steps == ["Define imports", "Define Config class", "Implement load()"]

    def test_llm_failure_returns_fallback(self):
        agent = _make_developer_agent(raise_exc=True)
        steps = agent._decompose_micro_steps("src/config.py", {})
        assert len(steps) == 1
        assert "config.py" in steps[0]

    def test_no_llm_client_returns_fallback(self):
        agent = DeveloperAgent(
            file_content_generator=MagicMock(),
            code_patcher=MagicMock(),
            locked_file_manager=MagicMock(),
            parallel_file_generator=MagicMock(),
            event_publisher=_make_ep(),
            logger=MagicMock(),
            tool_dispatcher=MagicMock(),
            instance_id=0,
            llm_client=None,
        )
        steps = agent._decompose_micro_steps("src/main.py", {})
        assert len(steps) == 1
        assert "main.py" in steps[0]

    def test_caps_at_seven_steps(self):
        raw = json.dumps([f"Step {i}" for i in range(10)])
        agent = _make_developer_agent(llm_response=raw)
        steps = agent._decompose_micro_steps("src/x.py", {})
        assert len(steps) <= 7

    def test_pads_to_three_when_fewer(self):
        raw = json.dumps(["Only one step"])
        agent = _make_developer_agent(llm_response=raw)
        steps = agent._decompose_micro_steps("src/x.py", {})
        assert len(steps) >= 3

    def test_invalid_json_returns_fallback(self):
        agent = _make_developer_agent(llm_response="NOT A JSON ARRAY")
        steps = agent._decompose_micro_steps("src/x.py", {})
        assert len(steps) == 1
        assert "x.py" in steps[0]

    def test_non_string_items_in_list_returns_fallback(self):
        raw = json.dumps([1, 2, 3])  # list of ints, not strings
        agent = _make_developer_agent(llm_response=raw)
        steps = agent._decompose_micro_steps("src/x.py", {})
        # Should fallback since not all items are strings
        assert len(steps) == 1

    def test_plan_steps_stored_on_node_task_data(self):
        """Integration: verify run() stores plan_steps into node.task_data."""
        raw = json.dumps(["Imports", "Dataclass", "Impl"])
        mock_client = MagicMock()
        mock_client.chat.return_value = ({"message": {"content": raw}}, None)

        mock_file_gen = MagicMock()
        mock_file_gen.generate_file_with_plan.return_value = "# generated content"

        agent = DeveloperAgent(
            file_content_generator=mock_file_gen,
            code_patcher=MagicMock(),
            locked_file_manager=MagicMock(),
            parallel_file_generator=MagicMock(),
            event_publisher=_make_ep(),
            logger=MagicMock(),
            tool_dispatcher=MagicMock(),
            instance_id=0,
            llm_client=mock_client,
        )

        node = MagicMock()
        node.task_data = {
            "file_path": "src/app.py",
            "plan": {"purpose": "Main app"},
            "is_remediation": False,
            "is_validation_fix": False,
            "prevention_tips": "",
            "remediation_actions": [],
            "context_deps": [],
        }

        blackboard = MagicMock()
        blackboard.read.return_value = None
        blackboard.write_sync = MagicMock()

        agent.run(node, blackboard)

        assert "plan_steps" in node.task_data
        assert isinstance(node.task_data["plan_steps"], list)
        assert len(node.task_data["plan_steps"]) >= 3
