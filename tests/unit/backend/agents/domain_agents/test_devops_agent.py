"""Unit tests for DevOpsAgent."""

import pytest
from unittest.mock import MagicMock
from backend.agents.domain_agents.devops_agent import DevOpsAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


def _make_ep():
    ep = MagicMock()
    ep.publish_sync = MagicMock()
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
    bb.write_sync = MagicMock()
    bb.get_all_generated_files.return_value = {"src/main.py": "def main(): pass"}
    return bb


@pytest.fixture
def mock_blackboard_unstable():
    bb = MagicMock()
    bb.read.return_value = False
    bb.write_sync = MagicMock()
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
    def test_skips_when_not_stable(self, devops, mock_blackboard_unstable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        result = devops.run(node, mock_blackboard_unstable)
        assert result == {}

    def test_generates_infra_when_stable(self, devops, mock_blackboard_stable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        result = devops.run(node, mock_blackboard_stable)
        assert len(result) >= 1

    def test_writes_infra_to_blackboard(self, devops, mock_blackboard_stable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        devops.run(node, mock_blackboard_stable)
        assert mock_blackboard_stable.write_sync.called

    def test_publishes_infra_generated_event(self, devops, mock_blackboard_stable):
        node = TaskNode(id="__devops__", agent_type=AgentType.DEVOPS, task_data={})
        devops.run(node, mock_blackboard_stable)
        event_calls = [c.args[0] for c in devops._event_publisher.publish_sync.call_args_list]
        assert "infra_generated" in event_calls

    def test_required_tools(self, devops):
        assert "infra_generator" in devops.REQUIRED_TOOLS
        assert "cicd_healer" in devops.REQUIRED_TOOLS
