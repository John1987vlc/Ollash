"""Unit tests for TaskDAG."""

import pytest
from backend.agents.orchestrators.task_dag import AgentType, CyclicDependencyError, TaskDAG, TaskNode, TaskStatus


@pytest.mark.unit
class TestTaskNode:
    def test_default_status_is_pending(self):
        node = TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={})
        assert node.status == TaskStatus.PENDING

    def test_to_dict_has_id(self):
        node = TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={})
        d = node.to_dict()
        assert d["id"] == "a.py"
        assert d["agent_type"] == "DEVELOPER"


@pytest.mark.unit
class TestTaskDAG:
    def test_add_task(self):
        dag = TaskDAG()
        node = TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={})
        dag.add_task(node)
        assert dag.get_node("a.py") is node

    def test_add_duplicate_raises(self):
        dag = TaskDAG()
        node = TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={})
        dag.add_task(node)
        with pytest.raises(ValueError, match="Duplicate"):
            dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))

    def test_get_ready_no_deps(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        dag.add_task(TaskNode(id="b.py", agent_type=AgentType.DEVELOPER, task_data={}))
        ready = dag.get_ready_tasks()
        assert len(ready) == 2

    def test_get_ready_respects_deps(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        dag.add_task(TaskNode(id="b.py", agent_type=AgentType.DEVELOPER, task_data={}, dependencies=["a.py"]))
        ready = dag.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "a.py"

    def test_mark_complete_unlocks_dependent(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        dag.add_task(TaskNode(id="b.py", agent_type=AgentType.DEVELOPER, task_data={}, dependencies=["a.py"]))
        dag.get_ready_tasks()  # mark a.py READY
        dag.mark_complete("a.py", result="content")
        ready = dag.get_ready_tasks()
        assert any(n.id == "b.py" for n in ready)

    def test_mark_failed(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        dag.mark_failed("a.py", "SyntaxError")
        assert dag.get_node("a.py").status == TaskStatus.FAILED
        assert dag.get_node("a.py").error == "SyntaxError"

    def test_is_complete_false_while_pending(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        assert not dag.is_complete()

    def test_is_complete_true_when_all_done(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        dag.get_ready_tasks()
        dag.mark_complete("a.py")
        assert dag.is_complete()

    def test_topological_sort_linear(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        dag.add_task(TaskNode(id="b.py", agent_type=AgentType.DEVELOPER, task_data={}, dependencies=["a.py"]))
        order = [n.id for n in dag.topological_sort()]
        assert order.index("a.py") < order.index("b.py")

    def test_topological_sort_cycle_raises(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="x.py", agent_type=AgentType.DEVELOPER, task_data={}, dependencies=["y.py"]))
        dag.add_task(TaskNode(id="y.py", agent_type=AgentType.DEVELOPER, task_data={}, dependencies=["x.py"]))
        with pytest.raises(CyclicDependencyError):
            dag.topological_sort()

    def test_stats_counts(self):
        dag = TaskDAG()
        dag.add_task(TaskNode(id="a.py", agent_type=AgentType.DEVELOPER, task_data={}))
        stats = dag.stats()
        assert stats["PENDING"] == 1
        assert stats["COMPLETED"] == 0
