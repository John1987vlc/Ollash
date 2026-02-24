"""Unit tests for DomainAgentOrchestrator."""
from pathlib import Path
import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.agents.domain_agent_orchestrator import DomainAgentOrchestrator
from backend.agents.orchestrators.task_dag import AgentType, TaskDAG, TaskNode


def make_simple_dag():
    dag = TaskDAG()
    dag.add_task(TaskNode(
        id="src/main.py", agent_type=AgentType.DEVELOPER,
        task_data={"file_path": "src/main.py"}
    ))
    dag.add_task(TaskNode(
        id="__devops__", agent_type=AgentType.DEVOPS,
        task_data={}, dependencies=["src/main.py"]
    ))
    dag.add_task(TaskNode(
        id="__auditor_final__", agent_type=AgentType.AUDITOR,
        task_data={}, dependencies=["__devops__"]
    ))
    return dag


@pytest.fixture
def mock_architect():
    arch = MagicMock()
    arch.run = AsyncMock(return_value=make_simple_dag())
    arch.plan_dag = AsyncMock(return_value=make_simple_dag())
    return arch


@pytest.fixture
def mock_developer():
    dev = MagicMock()
    dev.agent_id = "developer_0"
    dev.run = AsyncMock(return_value={"src/main.py": "def main(): pass\n"})
    return dev


@pytest.fixture
def mock_devops():
    d = MagicMock()
    d.run = AsyncMock(return_value={"Dockerfile": "FROM python\n"})
    return d


@pytest.fixture
def mock_auditor():
    a = MagicMock()
    a.run = AsyncMock(return_value={"total_files": 1, "newly_scanned": 1, "critical_files": []})
    a.set_blackboard = MagicMock()
    a.set_event_loop = MagicMock()
    return a


@pytest.fixture
def mock_blackboard():
    bb = MagicMock()
    bb.write = AsyncMock()
    bb.read.return_value = None
    bb.read_prefix.return_value = {}
    bb.get_all_generated_files.return_value = {"src/main.py": "code"}
    bb.snapshot.return_value = {}
    return bb


@pytest.fixture
def orchestrator(mock_architect, mock_developer, mock_devops, mock_auditor, mock_blackboard, tmp_path):
    return DomainAgentOrchestrator(
        architect_agent=mock_architect,
        developer_agent_pool=[mock_developer],
        devops_agent=mock_devops,
        auditor_agent=mock_auditor,
        blackboard=mock_blackboard,
        tool_dispatcher=MagicMock(),
        self_healing_loop=MagicMock(),
        locked_file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
        generated_projects_dir=tmp_path,
    )


@pytest.mark.unit
class TestDomainAgentOrchestrator:
    @pytest.mark.asyncio
    async def test_run_returns_path(self, orchestrator, tmp_path):
        result = await orchestrator.run("build api", "myapi")
        assert isinstance(result, Path)

    @pytest.mark.asyncio
    async def test_architect_plan_dag_called(self, orchestrator, mock_architect):
        await orchestrator.run("build api", "myapi")
        mock_architect.plan_dag.assert_called_once()

    @pytest.mark.asyncio
    async def test_auditor_set_blackboard_called(self, orchestrator, mock_auditor):
        await orchestrator.run("build api", "myapi")
        mock_auditor.set_blackboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_developer_run_called(self, orchestrator, mock_developer):
        await orchestrator.run("build api", "myapi")
        assert mock_developer.run.called

    def test_get_next_developer_round_robin(self, orchestrator, mock_developer):
        dev1 = orchestrator._get_next_developer()
        assert dev1 is mock_developer

    def test_get_next_developer_empty_pool_raises(self, orchestrator):
        orchestrator._dev_pool = []
        with pytest.raises(RuntimeError):
            orchestrator._get_next_developer()
