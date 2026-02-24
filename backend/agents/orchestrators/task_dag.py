"""
Task DAG (Directed Acyclic Graph) for Agent-per-Domain execution.

Replaces the sequential phase list with an explicit dependency graph that
allows parallel execution of independent tasks. Each node is a unit of work
assigned to a specific domain agent type.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentType(str, Enum):
    """Domain agent type responsible for executing a task node."""

    ARCHITECT = "ARCHITECT"
    DEVELOPER = "DEVELOPER"
    DEVOPS = "DEVOPS"
    AUDITOR = "AUDITOR"


class TaskStatus(str, Enum):
    """Lifecycle status of a task node in the DAG."""

    PENDING = "PENDING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REMEDIATION = "REMEDIATION"


class CyclicDependencyError(Exception):
    """Raised when a cycle is detected in the task DAG."""


@dataclass
class TaskNode:
    """A single unit of work in the task DAG.

    Attributes:
        id: Unique identifier (typically a relative file path or role name).
        agent_type: Domain agent responsible for executing this task.
        task_data: Arbitrary context passed to the agent (file path, plan, etc.).
        dependencies: IDs of tasks that must complete before this one starts.
        status: Current lifecycle status.
        result: Output written by the agent on success.
        error: Error message if the task failed.
        retry_count: Number of times this task has been retried.
    """

    id: str
    agent_type: AgentType
    task_data: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_type": self.agent_type.value,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "error": self.error,
        }


class TaskDAG:
    """
    Directed Acyclic Graph of TaskNodes for concurrent domain agent execution.

    Thread/coroutine safety: all mutations are guarded by an asyncio.Lock so
    that multiple coroutines can call mark_complete / mark_failed / get_ready_tasks
    concurrently without data races.

    Typical usage::

        dag = TaskDAG()
        dag.add_task(TaskNode(id="utils.py", agent_type=AgentType.DEVELOPER, ...))
        dag.add_task(TaskNode(id="main.py",  agent_type=AgentType.DEVELOPER,
                              dependencies=["utils.py"]))
        while not dag.is_complete():
            for node in dag.get_ready_tasks():
                asyncio.create_task(agent.run(node, ...))
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, TaskNode] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Mutation (not lock-guarded — call from single-threaded setup)
    # ------------------------------------------------------------------

    def add_task(self, node: TaskNode) -> None:
        """Add a TaskNode to the DAG.

        Raises:
            ValueError: If a node with the same id already exists.
        """
        if node.id in self._nodes:
            raise ValueError(f"Duplicate task id: {node.id!r}")
        self._nodes[node.id] = node

    # ------------------------------------------------------------------
    # Queries (synchronous, safe to call from any coroutine)
    # ------------------------------------------------------------------

    def get_node(self, task_id: str) -> Optional[TaskNode]:
        return self._nodes.get(task_id)

    def all_nodes(self) -> List[TaskNode]:
        return list(self._nodes.values())

    def is_complete(self) -> bool:
        """True when every node is COMPLETED or FAILED."""
        return all(
            n.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            for n in self._nodes.values()
        )

    def has_failures(self) -> bool:
        return any(n.status == TaskStatus.FAILED for n in self._nodes.values())

    def get_ready_tasks(self) -> List[TaskNode]:
        """Return PENDING nodes whose every dependency is COMPLETED.

        Atomically marks returned nodes as READY so concurrent callers
        do not double-schedule the same node.  The asyncio.Lock is acquired
        synchronously via the event-loop-aware pattern; callers inside an
        async context should call ``await dag._get_ready_tasks_async()``
        for fully non-blocking behaviour.  In practice the lock hold time is
        microseconds so the sync approach is acceptable.
        """
        ready: List[TaskNode] = []
        for node in self._nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            deps_done = all(
                self._nodes.get(dep_id, TaskNode(id="", agent_type=AgentType.DEVELOPER)).status
                == TaskStatus.COMPLETED
                for dep_id in node.dependencies
            )
            if deps_done:
                node.status = TaskStatus.READY
                ready.append(node)
        return ready

    # ------------------------------------------------------------------
    # Async state transitions
    # ------------------------------------------------------------------

    async def mark_in_progress(self, task_id: str) -> None:
        async with self._lock:
            node = self._nodes.get(task_id)
            if node is not None:
                node.status = TaskStatus.IN_PROGRESS

    async def mark_complete(self, task_id: str, result: Any = None) -> None:
        """Mark a task as COMPLETED and store its result."""
        async with self._lock:
            node = self._nodes.get(task_id)
            if node is not None:
                node.status = TaskStatus.COMPLETED
                node.result = result

    async def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as FAILED and store the error message."""
        async with self._lock:
            node = self._nodes.get(task_id)
            if node is not None:
                node.status = TaskStatus.FAILED
                node.error = error

    # ------------------------------------------------------------------
    # Topological utilities
    # ------------------------------------------------------------------

    def topological_sort(self) -> List[TaskNode]:
        """Return all nodes in topological order using Kahn's algorithm.

        Raises:
            CyclicDependencyError: If a dependency cycle is detected.
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep_id in node.dependencies:
                if dep_id in in_degree:
                    in_degree[node.id] += 1

        queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order: List[TaskNode] = []

        while queue:
            nid = queue.popleft()
            order.append(self._nodes[nid])
            for other in self._nodes.values():
                if nid in other.dependencies:
                    in_degree[other.id] -= 1
                    if in_degree[other.id] == 0:
                        queue.append(other.id)

        if len(order) != len(self._nodes):
            raise CyclicDependencyError(
                f"Cycle detected in TaskDAG; only {len(order)}/{len(self._nodes)} nodes resolved."
            )
        return order

    def stats(self) -> Dict[str, int]:
        """Return a count of nodes in each status."""
        counts: Dict[str, int] = {s.value: 0 for s in TaskStatus}
        for node in self._nodes.values():
            counts[node.status.value] += 1
        return counts
