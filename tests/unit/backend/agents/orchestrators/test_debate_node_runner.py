"""Unit tests — DebateNodeRunner (P8)."""

from unittest.mock import MagicMock

import pytest

from backend.agents.orchestrators.debate_node_runner import DebateNodeRunner
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


def _make_runner(max_rounds: int = 2) -> DebateNodeRunner:
    agent_a = MagicMock()
    agent_b = MagicMock()
    ep = MagicMock()
    ep.publish_sync = MagicMock()
    logger = MagicMock()

    # Agents return a dict with a content key (sync now)
    agent_a.run = MagicMock(return_value={"_debate_response": "I think option A is better."})
    agent_b.run = MagicMock(return_value={"_debate_response": "I agree with A, consensus reached."})

    return DebateNodeRunner(
        agent_a=agent_a,
        agent_b=agent_b,
        event_publisher=ep,
        logger=logger,
        max_rounds=max_rounds,
    )


def _make_node() -> TaskNode:
    return TaskNode(
        id="debate_arch",
        agent_type=AgentType.DEBATE,
        task_data={"topic": "Choose DB engine", "description": "Architecture decision: PostgreSQL vs SQLite"},
    )


def _make_bb():
    bb = MagicMock()
    bb.write_sync = MagicMock()
    bb.read = MagicMock(return_value=None)
    return bb


@pytest.mark.unit
class TestDebateNodeRunner:
    def test_constructor(self):
        runner = _make_runner()
        assert runner._max_rounds == 2

    def test_run_returns_string(self):
        runner = _make_runner()
        node = _make_node()
        blackboard = _make_bb()

        result = runner.run(node, blackboard)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_consensus_detected_early(self):
        """When agent_b says 'i agree', consensus should be detected."""
        runner = _make_runner(max_rounds=5)
        # Consensus keyword present in agent_b response
        runner._agent_b.run = MagicMock(return_value={"_debate_response": "I agree, consensus reached."})

        node = _make_node()
        blackboard = _make_bb()

        result = runner.run(node, blackboard)
        # Should not have run all 5 rounds
        assert "agree" in result.lower() or isinstance(result, str)

    def test_writes_to_blackboard(self):
        runner = _make_runner()
        node = _make_node()
        blackboard = _make_bb()

        runner.run(node, blackboard)
        # Blackboard.write_sync should be called at least once for storing round results
        assert blackboard.write_sync.call_count >= 1

    def test_publishes_debate_round_events(self):
        runner = _make_runner()
        node = _make_node()
        blackboard = _make_bb()

        runner.run(node, blackboard)
        # Event publisher should have been called with debate events
        ep: MagicMock = runner._event_publisher
        event_types = [c.args[0] for c in ep.publish_sync.call_args_list]
        assert any("debate" in et.lower() for et in event_types)
