"""Unit tests for DeveloperAgent."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.agents.domain_agents.developer_agent import DeveloperAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


@pytest.fixture
def mock_file_gen():
    fg = MagicMock()
    fg.generate_file_with_plan.return_value = "def main(): pass\n"
    fg.generate_file.return_value = "def main(): pass\n"
    return fg


@pytest.fixture
def mock_blackboard():
    bb = MagicMock()
    bb.read.return_value = None
    bb.write = AsyncMock()
    bb.get_all_generated_files.return_value = {}
    return bb


@pytest.fixture
def developer(mock_file_gen):
    return DeveloperAgent(
        file_content_generator=mock_file_gen,
        code_patcher=MagicMock(),
        locked_file_manager=MagicMock(),
        parallel_file_generator=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
        tool_dispatcher=MagicMock(),
        instance_id=0,
    )


@pytest.mark.unit
class TestDeveloperAgent:
    @pytest.mark.asyncio
    async def test_run_returns_file_dict(self, developer, mock_blackboard):
        node = TaskNode(
            id="src/main.py", agent_type=AgentType.DEVELOPER, task_data={"file_path": "src/main.py", "plan": {}}
        )
        result = await developer.run(node, mock_blackboard)
        assert "src/main.py" in result
        assert isinstance(result["src/main.py"], str)

    @pytest.mark.asyncio
    async def test_run_writes_to_blackboard(self, developer, mock_blackboard):
        node = TaskNode(
            id="src/main.py", agent_type=AgentType.DEVELOPER, task_data={"file_path": "src/main.py", "plan": {}}
        )
        await developer.run(node, mock_blackboard)
        mock_blackboard.write.assert_called_once()
        call_key = mock_blackboard.write.call_args.args[0]
        assert "generated_files/src/main.py" in call_key

    @pytest.mark.asyncio
    async def test_run_publishes_file_generated_event(self, developer, mock_blackboard):
        node = TaskNode(
            id="src/main.py", agent_type=AgentType.DEVELOPER, task_data={"file_path": "src/main.py", "plan": {}}
        )
        await developer.run(node, mock_blackboard)
        developer._event_publisher.publish.assert_called_with(
            "file_generated",
            file_path="src/main.py",
            agent_id="developer_0",
            content="def main(): pass\n",
            content_preview="def main(): pass\n"[:200],
            is_remediation=False,
        )

    @pytest.mark.asyncio
    async def test_small_file_init_py_returns_empty(self, developer, mock_blackboard):
        node = TaskNode(
            id="src/__init__.py", agent_type=AgentType.DEVELOPER, task_data={"file_path": "src/__init__.py", "plan": {}}
        )
        result = await developer.run(node, mock_blackboard)
        content = result["src/__init__.py"]
        assert isinstance(content, str)  # Could be empty string or stub

    def test_is_small_file_init(self):
        assert DeveloperAgent._is_small_file("src/__init__.py") is True

    def test_is_small_file_regular(self):
        assert DeveloperAgent._is_small_file("src/main.py") is False

    def test_agent_id_uses_instance_id(self, mock_file_gen):
        agent = DeveloperAgent(
            file_content_generator=mock_file_gen,
            code_patcher=MagicMock(),
            locked_file_manager=MagicMock(),
            parallel_file_generator=MagicMock(),
            event_publisher=MagicMock(),
            logger=MagicMock(),
            tool_dispatcher=MagicMock(),
            instance_id=2,
        )
        assert agent.agent_id == "developer_2"
