"""Unit tests for F4 — CriticAgent."""

import pytest
from unittest.mock import MagicMock

from backend.agents.domain_agents.critic_agent import CriticAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


def _make_ep():
    ep = MagicMock()
    ep.publish_sync = MagicMock()
    return ep


@pytest.fixture
def mock_ekb():
    ekb = MagicMock()
    ekb.query_similar_errors.return_value = []
    return ekb


@pytest.fixture
def agent(mock_ekb):
    return CriticAgent(
        error_knowledge_base=mock_ekb,
        event_publisher=_make_ep(),
        logger=MagicMock(),
        tool_dispatcher=MagicMock(),
    )


@pytest.fixture
def blackboard():
    bb = MagicMock()
    bb.get_all_generated_files.return_value = {}
    bb.write_sync = MagicMock()
    return bb


@pytest.fixture
def node():
    return TaskNode(id="critic", agent_type=AgentType.CRITIC)


@pytest.mark.unit
class TestCriticAgentRun:
    def test_no_files_returns_zero_count(self, agent, blackboard, node):
        result = agent.run(node, blackboard)
        assert result["critique_count"] == 0

    def test_queries_ekb_per_file(self, agent, blackboard, node, mock_ekb):
        blackboard.get_all_generated_files.return_value = {
            "src/app.py": "def main(): pass",
            "src/utils.py": "def helper(): pass",
        }
        mock_ekb.query_similar_errors.return_value = []
        agent.run(node, blackboard)
        assert mock_ekb.query_similar_errors.call_count == 2

    def test_writes_critique_to_blackboard_when_patterns_found(self, agent, blackboard, node, mock_ekb):
        blackboard.get_all_generated_files.return_value = {"src/app.py": "code"}
        pattern = MagicMock()
        pattern.prevention_tip = "Avoid mutable default args"
        mock_ekb.query_similar_errors.return_value = [pattern]

        result = agent.run(node, blackboard)

        blackboard.write_sync.assert_called_once()
        call_args = blackboard.write_sync.call_args
        assert call_args[0][0] == "critique/src/app.py"
        assert result["critique_count"] == 1

    def test_skips_empty_content(self, agent, blackboard, node, mock_ekb):
        blackboard.get_all_generated_files.return_value = {"src/empty.py": ""}
        agent.run(node, blackboard)
        mock_ekb.query_similar_errors.assert_not_called()


@pytest.mark.unit
class TestInferLanguage:
    def test_py_is_python(self):
        assert CriticAgent._infer_language("src/main.py") == "python"

    def test_ts_is_typescript(self):
        assert CriticAgent._infer_language("app.ts") == "typescript"

    def test_unknown_extension(self):
        assert CriticAgent._infer_language("file.xyz") == "unknown"
