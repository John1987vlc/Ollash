"""Unit tests for F4 — TacticalAgent."""

import pytest
from unittest.mock import MagicMock

from backend.agents.domain_agents.tactical_agent import TacticalAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


@pytest.fixture
def mock_patcher():
    p = MagicMock()
    p.apply_search_replace.return_value = ("", [])
    return p


@pytest.fixture
def mock_validator():
    v = MagicMock()
    v.validate_syntax_immediate.return_value = None  # No error
    return v


@pytest.fixture
def mock_event_publisher():
    ep = MagicMock()
    ep.publish_sync = MagicMock()
    return ep


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_tool_dispatcher():
    return MagicMock()


@pytest.fixture
def agent(mock_patcher, mock_validator, mock_event_publisher, mock_logger, mock_tool_dispatcher):
    return TacticalAgent(
        code_patcher=mock_patcher,
        file_validator=mock_validator,
        event_publisher=mock_event_publisher,
        logger=mock_logger,
        tool_dispatcher=mock_tool_dispatcher,
        llm_client=None,
    )


@pytest.fixture
def blackboard():
    bb = MagicMock()
    bb.read = MagicMock(return_value="def target():\n    pass\n")
    bb.write_sync = MagicMock()
    return bb


@pytest.mark.unit
class TestTacticalAgentRun:
    def test_raises_if_missing_task_data(self, agent, blackboard):
        node = TaskNode(id="t", agent_type=AgentType.TACTICAL)
        with pytest.raises(ValueError, match="file_path"):
            agent.run(node, blackboard)

    def test_raises_if_no_content_on_blackboard(self, agent, blackboard):
        blackboard.read.return_value = ""
        node = TaskNode(
            id="t",
            agent_type=AgentType.TACTICAL,
            task_data={"file_path": "f.py", "function_name": "target"},
        )
        with pytest.raises(RuntimeError, match="no content"):
            agent.run(node, blackboard)

    def test_skips_when_function_not_found(self, agent, blackboard):
        blackboard.read.return_value = "def other(): pass\n"
        node = TaskNode(
            id="t",
            agent_type=AgentType.TACTICAL,
            task_data={"file_path": "f.py", "function_name": "missing_func"},
        )
        result = agent.run(node, blackboard)
        assert "Skipped" in result["context_note"]

    def test_patch_failure_returns_original(self, agent, blackboard, mock_patcher):
        blackboard.read.return_value = "def target():\n    pass\n"
        mock_patcher.apply_search_replace.return_value = ("", ["def target():\n    pass\n"])
        node = TaskNode(
            id="t",
            agent_type=AgentType.TACTICAL,
            task_data={"file_path": "f.py", "function_name": "target"},
        )
        # No LLM client → _generate_implementation returns ""
        result = agent.run(node, blackboard)
        # No improvement generated → early return
        assert "context_note" in result


@pytest.mark.unit
class TestExtractFunctionBlock:
    def test_extracts_simple_function(self):
        content = "def foo():\n    return 1\n\ndef bar():\n    pass\n"
        block = TacticalAgent._extract_function_block(content, "foo")
        assert "def foo" in block
        assert "def bar" not in block

    def test_returns_empty_for_missing_function(self):
        block = TacticalAgent._extract_function_block("def other(): pass\n", "missing")
        assert block == ""

    def test_returns_empty_for_syntax_error(self):
        block = TacticalAgent._extract_function_block("def (broken syntax:", "foo")
        assert block == ""
