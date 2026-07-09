"""Unit tests — LangGraphSwarmOrchestrator."""

from unittest.mock import MagicMock
from pathlib import Path
import pytest

from backend.agents.orchestrators.langgraph_orchestrator import LangGraphSwarmOrchestrator, SwarmState
from backend.agents.orchestrators.task_dag import TaskDAG, TaskNode, AgentType


def _make_mock_architect() -> MagicMock:
    architect = MagicMock()
    # Mock plan_dag to return a simple TaskDAG with 1 developer task
    dag = TaskDAG()
    node = TaskNode(
        id="dev_file_py",
        agent_type=AgentType.DEVELOPER,
        task_data={"file_path": "main.py", "plan": {"code": "print('hello')"}}
    )
    dag.add_task(node)
    
    architect.plan_dag = MagicMock(return_value=dag)
    return architect


def _make_mock_developer() -> MagicMock:
    developer = MagicMock()
    developer.run = MagicMock(return_value={"main.py": "print('hello')"})
    return developer


def _make_mock_devops() -> MagicMock:
    devops = MagicMock()
    devops.run = MagicMock(return_value={})
    return devops


def _make_mock_auditor() -> MagicMock:
    auditor = MagicMock()
    auditor.run = MagicMock(return_value={})
    return auditor


def _make_bb():
    bb = MagicMock()
    bb.write_sync = MagicMock()
    bb.read = MagicMock(return_value=None)
    bb.clear = MagicMock()
    return bb


@pytest.mark.unit
class TestLangGraphSwarmOrchestrator:
    def test_constructor(self):
        arch = _make_mock_architect()
        dev = _make_mock_developer()
        devops = _make_mock_devops()
        aud = _make_mock_auditor()
        bb = _make_bb()
        logger = MagicMock()
        
        orchestrator = LangGraphSwarmOrchestrator(
            architect_agent=arch,
            developer_agent=dev,
            devops_agent=devops,
            auditor_agent=aud,
            blackboard=bb,
            logger=logger,
            generated_projects_dir=Path(".ollash/test_projects")
        )
        assert orchestrator._architect == arch
        assert orchestrator._developer == dev

    def test_run_success_flow(self, tmp_path):
        arch = _make_mock_architect()
        dev = _make_mock_developer()
        devops = _make_mock_devops()
        aud = _make_mock_auditor()
        bb = _make_bb()
        logger = MagicMock()

        # Mock blackboard read to return no errors during audit
        bb.read = MagicMock(side_effect=lambda key, default=None: {
            "project_path": str(tmp_path / "test_proj"),
            "project_name": "test_proj",
            "audit_report": {"issues": []}
        }.get(key, default))

        orchestrator = LangGraphSwarmOrchestrator(
            architect_agent=arch,
            developer_agent=dev,
            devops_agent=devops,
            auditor_agent=aud,
            blackboard=bb,
            logger=logger,
            generated_projects_dir=tmp_path
        )

        project_path = orchestrator.run(
            project_description="Create hello world app",
            project_name="test_proj"
        )
        
        # Verify execution path
        assert arch.plan_dag.call_count == 1
        assert dev.run.call_count == 1
        assert aud.run.call_count == 1
        assert devops.run.call_count == 1
        
        # Verify output path
        assert Path(project_path).name == "test_proj"
        assert bb.clear.call_count == 1
