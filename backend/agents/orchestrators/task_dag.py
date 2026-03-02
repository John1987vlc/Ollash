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
    DEBATE = "DEBATE"
    # F4: Granularity sub-roles for small model specialisation
    TACTICAL = "TACTICAL"  # Single-function implementation (prohibits touching other functions)
    CRITIC = "CRITIC"  # Error pattern detection via ErrorKnowledgeBase (no LLM calls)


class TaskStatus(str, Enum):
    """Lifecycle status of a task node in the DAG."""

    PENDING = "PENDING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REMEDIATION = "REMEDIATION"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    BLOCKED = "BLOCKED"


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
        hitl_question: Question posed to the user when status is WAITING_FOR_USER.
        hitl_answer: Answer provided by the user; triggers transition back to PENDING.
        debate_agents: Agent types participating in a DEBATE node.
        debate_rounds: Maximum rounds for a DEBATE node.
    """

    id: str
    agent_type: AgentType
    task_data: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    hitl_question: Optional[str] = None
    hitl_answer: Optional[str] = None
    debate_agents: List[str] = field(default_factory=list)
    debate_rounds: int = 3
    # F5: Short-term memory note written by the agent after task completion.
    # Injected as context into the next dependent task's messages.
    context_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result_preview = ""
        if self.result is not None:
            raw = str(self.result)
            result_preview = raw[:200] + ("..." if len(raw) > 200 else "")
        return {
            "id": self.id,
            "agent_type": self.agent_type.value,
            "task_data": self.task_data,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "error": self.error,
            "hitl_question": self.hitl_question,
            "hitl_answer": self.hitl_answer,
            "debate_agents": self.debate_agents,
            "debate_rounds": self.debate_rounds,
            "context_note": self.context_note,
            "result_preview": result_preview,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskNode":
        return cls(
            id=data["id"],
            agent_type=AgentType(data["agent_type"]),
            task_data=data.get("task_data", {}),
            dependencies=data.get("dependencies", []),
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            result=None,  # Results are not serialised (content lives on Blackboard)
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            hitl_question=data.get("hitl_question"),
            hitl_answer=data.get("hitl_answer"),
            debate_agents=data.get("debate_agents", []),
            debate_rounds=data.get("debate_rounds", 3),
            context_note=data.get("context_note"),
        )


# Sentinel used as a default in get_ready_tasks dependency checks so we
# never construct a full TaskNode just to evaluate a missing dep_id.
_DUMMY_NODE = TaskNode(id="__dummy__", agent_type=AgentType.DEVELOPER)


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
            for node in await dag.get_ready_tasks():
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
        """True when every node is COMPLETED or FAILED (not blocked/waiting)."""
        terminal = (TaskStatus.COMPLETED, TaskStatus.FAILED)
        return all(n.status in terminal for n in self._nodes.values())

    def has_failures(self) -> bool:
        return any(n.status == TaskStatus.FAILED for n in self._nodes.values())

    async def get_ready_tasks(self) -> List[TaskNode]:
        """Return PENDING nodes whose every dependency is COMPLETED.

        Atomically marks returned nodes as READY under the asyncio.Lock so
        that concurrent callers cannot double-schedule the same node.
        """
        ready: List[TaskNode] = []
        async with self._lock:
            for node in self._nodes.values():
                if node.status != TaskStatus.PENDING:
                    continue
                deps_done = all(
                    self._nodes.get(dep_id, _DUMMY_NODE).status == TaskStatus.COMPLETED for dep_id in node.dependencies
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

    async def mark_waiting(self, task_id: str, question: str) -> None:
        """Pause a task awaiting human input.

        The DAG loop will skip this node until ``mark_unblocked`` is called
        with the user's answer, at which point the node returns to PENDING
        and re-enters the normal execution queue.
        """
        async with self._lock:
            node = self._nodes.get(task_id)
            if node is not None:
                node.status = TaskStatus.WAITING_FOR_USER
                node.hitl_question = question
                node.hitl_answer = None

    async def mark_unblocked(self, task_id: str, answer: str) -> None:
        """Receive a user answer and re-queue the node as PENDING."""
        async with self._lock:
            node = self._nodes.get(task_id)
            if node is not None and node.status == TaskStatus.WAITING_FOR_USER:
                node.hitl_answer = answer
                node.status = TaskStatus.PENDING

    def get_waiting_nodes(self) -> List[TaskNode]:
        """Return all nodes currently waiting for user input."""
        return [n for n in self._nodes.values() if n.status == TaskStatus.WAITING_FOR_USER]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the entire DAG to a JSON-compatible dict."""
        return {"nodes": [node.to_dict() for node in self._nodes.values()]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskDAG":
        """Reconstruct a TaskDAG from a serialised dict."""
        dag = cls()
        for node_data in data.get("nodes", []):
            dag.add_task(TaskNode.from_dict(node_data))
        return dag

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
