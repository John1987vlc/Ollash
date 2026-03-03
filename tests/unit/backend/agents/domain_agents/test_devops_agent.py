"""Unit tests for DevOpsAgent."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.agents.domain_agents.devops_agent import DevOpsAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


def _make_ep():
    ep = MagicMock()
    ep.publish = AsyncMock()
    return ep


@pytest.fixture
def mock_infra_gen():
    ig = MagicMock()
    ig.generate.return_value = {
        "Dockerfile": "FROM python:3.11\n",
        "docker-compose.yml": "version: '3'\n",
    }
    return ig


@pytest.fixture
def mock_blackboard_stable():
    bb = MagicMock()

    def bb_read(key, default=None):
        data = {
            "codebase_stable": True,
            "project_name": "myapi",
            "project_description": "REST API",
            "ci_failures": None,
        }
        return data.get(key, default)

    bb.read = bb_read
    bb.write = AsyncMock()
    bb.get_all_generated_files.return_value = {"src/main.py": "def main(): pass"}
    return bb


@pytest.fixture
def mock_blackboard_unstable():
    bb = MagicMock()
    bb.read.return_value = False
    bb.write = AsyncMock()
    bb.get_all_generated_files.return_value = {}
    return bb


@pytest.fixture
def devops(mock_infra_gen):
    return DevOpsAgent(
        infra_generator=mock_infra_gen,
        cicd_healer=MagicMock(),
        event_publisher=_make_ep(),
        logger=MagicMock(),
        tool_dispatcher=MagicMock(),
    )


@pytest.mark.unit
class TestDevOpsAgent:
    @pytest.mark.asyncio
    async def test_skips_when_not_stable(self, devops, mock_blackboard_unstable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        result = await devops.run(node, mock_blackboard_unstable)
        assert result == {}

    @pytest.mark.asyncio
    async def test_generates_infra_when_stable(self, devops, mock_blackboard_stable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        result = await devops.run(node, mock_blackboard_stable)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_writes_infra_to_blackboard(self, devops, mock_blackboard_stable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        await devops.run(node, mock_blackboard_stable)
        assert mock_blackboard_stable.write.called

    @pytest.mark.asyncio
    async def test_publishes_infra_generated_event(self, devops, mock_blackboard_stable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        await devops.run(node, mock_blackboard_stable)
        event_calls = [c.args[0] for c in devops._event_publisher.publish.call_args_list]
        assert "infra_generated" in event_calls

    def test_required_tools(self, devops):
        assert "infra_generator" in devops.REQUIRED_TOOLS
        assert "cicd_healer" in devops.REQUIRED_TOOLS
