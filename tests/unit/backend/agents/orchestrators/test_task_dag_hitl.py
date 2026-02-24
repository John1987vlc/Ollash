"""Unit tests — TaskDAG HITL extensions (P1)."""

import pytest

from backend.agents.orchestrators.task_dag import AgentType, TaskDAG, TaskNode, TaskStatus


@pytest.mark.unit
class TestTaskDAGHITL:
    """Tests for mark_waiting / mark_unblocked / get_waiting_nodes."""

    def _make_dag(self) -> TaskDAG:
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="node_a",
                task_description="Generate foo.py",
                agent_type=AgentType.DEVELOPER,
                task_data={"file_path": "foo.py"},
            )
        )
        return dag

    @pytest.mark.asyncio
    async def test_mark_waiting_sets_status_and_question(self):
        dag = self._make_dag()
        await dag.mark_waiting("node_a", "Should I overwrite existing file?")
        node = dag.get_node("node_a")
        assert node.status == TaskStatus.WAITING_FOR_USER
        assert node.hitl_question == "Should I overwrite existing file?"

    @pytest.mark.asyncio
    async def test_mark_unblocked_resets_to_pending(self):
        dag = self._make_dag()
        await dag.mark_waiting("node_a", "Question?")
        await dag.mark_unblocked("node_a", "yes, proceed")
        node = dag.get_node("node_a")
        assert node.status == TaskStatus.PENDING
        assert node.hitl_answer == "yes, proceed"

    @pytest.mark.asyncio
    async def test_get_waiting_nodes_returns_only_waiting(self):
        dag = self._make_dag()
        dag.add_node(
            TaskNode(
                id="node_b",
                task_description="Generate bar.py",
                agent_type=AgentType.DEVELOPER,
                task_data={"file_path": "bar.py"},
            )
        )
        await dag.mark_waiting("node_a", "Question?")
        waiting = dag.get_waiting_nodes()
        ids = [n.id for n in waiting]
        assert "node_a" in ids
        assert "node_b" not in ids

    @pytest.mark.asyncio
    async def test_is_complete_ignores_waiting_nodes(self):
        dag = self._make_dag()
        await dag.mark_waiting("node_a", "Question?")
        # DAG should NOT be complete — WAITING_FOR_USER is not terminal
        assert not dag.is_complete()

    @pytest.mark.asyncio
    async def test_mark_waiting_unknown_node_no_error(self):
        """Marking an unknown node should not raise."""
        dag = self._make_dag()
        # Should not raise; just silently no-op
        await dag.mark_waiting("does_not_exist", "?")


@pytest.mark.unit
class TestTaskDAGSerialization:
    """Tests for to_dict / from_dict round-trip (P2 checkpointing)."""

    def _make_dag(self) -> TaskDAG:
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="n1",
                task_description="Write models.py",
                agent_type=AgentType.DEVELOPER,
                task_data={"file_path": "models.py"},
            )
        )
        dag.add_node(
            TaskNode(
                id="n2",
                task_description="Setup infra",
                agent_type=AgentType.DEVOPS,
                task_data={},
                dependencies=["n1"],
            )
        )
        return dag

    def test_round_trip_preserves_nodes(self):
        dag = self._make_dag()
        d = dag.to_dict()
        dag2 = TaskDAG.from_dict(d)
        assert "n1" in [n.id for n in dag2.nodes]
        assert "n2" in [n.id for n in dag2.nodes]

    def test_round_trip_preserves_dependencies(self):
        dag = self._make_dag()
        dag2 = TaskDAG.from_dict(dag.to_dict())
        n2 = dag2.get_node("n2")
        assert "n1" in n2.dependencies

    def test_round_trip_preserves_hitl_fields(self):
        dag = self._make_dag()
        dag.get_node("n1").hitl_question = "Confirm?"
        dag.get_node("n1").hitl_answer = "yes"
        dag2 = TaskDAG.from_dict(dag.to_dict())
        n1 = dag2.get_node("n1")
        assert n1.hitl_question == "Confirm?"
        assert n1.hitl_answer == "yes"
