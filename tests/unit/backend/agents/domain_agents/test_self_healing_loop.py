"""Unit tests for SelfHealingLoop."""

import pytest
from unittest.mock import MagicMock
from backend.agents.orchestrators.self_healing_loop import SelfHealingLoop
from backend.agents.orchestrators.task_dag import AgentType, TaskDAG, TaskNode


def _make_ep():
    ep = MagicMock()
    ep.publish_sync = MagicMock()
    return ep


@pytest.fixture
def mock_ekb():
    ekb = MagicMock()
    ekb.record_error.return_value = "pattern_abc123"
    ekb.get_patterns_for_file.return_value = []
    return ekb


@pytest.fixture
def mock_cp():
    cp = MagicMock()
    cp.generate_contingency_plan.return_value = {"actions": [{"type": "modify_file", "path": "src/a.py"}]}
    return cp


@pytest.fixture
def healing_loop(mock_ekb, mock_cp):
    return SelfHealingLoop(
        error_knowledge_base=mock_ekb,
        contingency_planner=mock_cp,
        event_publisher=_make_ep(),
        logger=MagicMock(),
        max_retries=2,
    )


@pytest.mark.unit
class TestSelfHealingLoop:
    def test_handle_failure_creates_remediation_node(self, healing_loop, mock_ekb, mock_cp):
        dag = TaskDAG()
        failed_node = TaskNode(
            id="src/a.py", agent_type=AgentType.DEVELOPER, task_data={"file_path": "src/a.py"}, error="SyntaxError"
        )
        dag.add_task(failed_node)
        bb = MagicMock()
        bb.snapshot.return_value = {}

        result = healing_loop.handle_failure(failed_node, dag, bb, "build api", "# README")

        assert result.success is True
        assert "remediate_src/a.py" in result.remediation_task_id
        mock_ekb.record_error.assert_called_once()
        mock_cp.generate_contingency_plan.assert_called_once()

    def test_remediation_node_in_dag(self, healing_loop):
        dag = TaskDAG()
        failed_node = TaskNode(id="x.py", agent_type=AgentType.DEVELOPER, task_data={}, error="err")
        dag.add_task(failed_node)

        result = healing_loop.handle_failure(failed_node, dag, MagicMock(), "desc", "readme")

        assert dag.get_node(result.remediation_task_id) is not None

    def test_no_remediation_after_max_retries(self, healing_loop, mock_ekb, mock_cp):
        dag = TaskDAG()
        exhausted = TaskNode(id="z.py", agent_type=AgentType.DEVELOPER, task_data={}, error="err", retry_count=2)
        dag.add_task(exhausted)

        result = healing_loop.handle_failure(exhausted, dag, MagicMock(), "desc", "readme")

        assert result.success is False
        assert result.error is not None
        mock_cp.generate_contingency_plan.assert_not_called()

    def test_handle_validation_failure(self, healing_loop):
        dag = TaskDAG()
        result = healing_loop.handle_validation_failure(
            file_path="src/model.py",
            content="def foo():\n  pass",
            error="Missing type hints",
            dag=dag,
            blackboard=MagicMock(),
        )
        assert result.success is True
        assert dag.get_node(result.remediation_task_id) is not None

    def test_classify_error_syntax(self, healing_loop):
        assert healing_loop._classify_error("SyntaxError: invalid syntax") == "syntax"

    def test_classify_error_import(self, healing_loop):
        assert healing_loop._classify_error("ModuleNotFoundError: No module named 'foo'") == "import"

    def test_classify_error_default(self, healing_loop):
        assert healing_loop._classify_error("random error") == "generation"
