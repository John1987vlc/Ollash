"""Unit tests for ArchitectAgent."""

import pytest
from unittest.mock import MagicMock
from backend.agents.domain_agents.architect_agent import ArchitectAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskDAG


def _make_ep():
    ep = MagicMock()
    ep.publish_sync = MagicMock()
    return ep


def _make_bb():
    bb = MagicMock()
    bb.read.return_value = None
    bb.write_sync = MagicMock()
    return bb


@pytest.fixture
def mock_dep_graph():
    g = MagicMock()
    g.build_from_structure.return_value = None
    g.get_generation_order.return_value = ["src/utils.py", "src/main.py"]
    g.get_context_for_file.return_value = []
    return g


@pytest.fixture
def mock_structure_gen():
    sg = MagicMock()
    sg.generate.return_value = {
        "folders": [{"name": "src", "files": ["utils.py", "main.py"], "folders": []}],
        "files": [],
    }
    return sg


@pytest.fixture
def architect(mock_dep_graph, mock_structure_gen):
    return ArchitectAgent(
        dependency_graph=mock_dep_graph,
        structure_generator=mock_structure_gen,
        prompt_loader=MagicMock(),
        event_publisher=_make_ep(),
        logger=MagicMock(),
        tool_dispatcher=MagicMock(),
    )


@pytest.mark.unit
class TestArchitectAgent:
    def test_plan_dag_returns_taskdag(self, architect):
        bb = _make_bb()
        dag = architect.plan_dag("build api", "myapi", bb)
        assert isinstance(dag, TaskDAG)

    def test_dag_has_developer_nodes(self, architect):
        bb = _make_bb()
        dag = architect.plan_dag("build api", "myapi", bb)
        dev_nodes = [n for n in dag.all_nodes() if n.agent_type == AgentType.DEVELOPER]
        assert len(dev_nodes) >= 1

    def test_dag_has_devops_node(self, architect):
        bb = _make_bb()
        dag = architect.plan_dag("build api", "myapi", bb)
        devops_nodes = [n for n in dag.all_nodes() if n.agent_type == AgentType.DEVOPS]
        assert len(devops_nodes) == 1

    def test_dag_has_auditor_node(self, architect):
        bb = _make_bb()
        dag = architect.plan_dag("build api", "myapi", bb)
        auditor_nodes = [n for n in dag.all_nodes() if n.agent_type == AgentType.AUDITOR]
        assert len(auditor_nodes) == 1

    def test_writes_to_blackboard(self, architect):
        bb = _make_bb()
        architect.plan_dag("build api", "myapi", bb)
        written_keys = [c.args[0] for c in bb.write_sync.call_args_list]
        assert "task_dag" in written_keys
        assert "codebase_stable" in written_keys

    def test_uses_existing_structure_from_blackboard(self, architect, mock_structure_gen):
        existing_structure = {"folders": [], "files": ["main.py"]}
        bb = _make_bb()
        bb.read.side_effect = lambda key, *args: existing_structure if key == "project_structure" else None
        architect.plan_dag("build api", "myapi", bb)
        mock_structure_gen.generate.assert_not_called()

    def test_get_tool_prompt_section(self, architect):
        section = architect._get_tool_prompt_section()
        assert "dependency_graph" in section
        assert "structure_generator" in section
