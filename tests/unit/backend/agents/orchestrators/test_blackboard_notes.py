"""Unit tests for F5 — Blackboard context notes in TaskNode + DomainAgentOrchestrator."""

import pytest

from backend.agents.orchestrators.task_dag import AgentType, TaskNode


@pytest.mark.unit
class TestTaskNodeContextNote:
    """TaskNode.context_note serialization."""

    def test_context_note_defaults_to_none(self):
        node = TaskNode(id="test", agent_type=AgentType.DEVELOPER)
        assert node.context_note is None

    def test_context_note_serialised_in_to_dict(self):
        node = TaskNode(id="t", agent_type=AgentType.DEVELOPER, context_note="my note")
        d = node.to_dict()
        assert d["context_note"] == "my note"

    def test_context_note_deserialised_from_dict(self):
        data = {
            "id": "t",
            "agent_type": "DEVELOPER",
            "context_note": "restored note",
        }
        node = TaskNode.from_dict(data)
        assert node.context_note == "restored note"

    def test_context_note_none_round_trip(self):
        node = TaskNode(id="t", agent_type=AgentType.DEVELOPER)
        d = node.to_dict()
        node2 = TaskNode.from_dict(d)
        assert node2.context_note is None


@pytest.mark.unit
class TestAgentTypeExtended:
    """F4 + F5 — TACTICAL and CRITIC are valid AgentType values."""

    def test_tactical_agent_type_exists(self):
        assert AgentType.TACTICAL.value == "TACTICAL"

    def test_critic_agent_type_exists(self):
        assert AgentType.CRITIC.value == "CRITIC"

    def test_tactical_node_round_trip(self):
        node = TaskNode(id="tf", agent_type=AgentType.TACTICAL)
        d = node.to_dict()
        node2 = TaskNode.from_dict(d)
        assert node2.agent_type == AgentType.TACTICAL
