"""
Domain Agent Orchestrator — Entry Point for Agent-per-Domain Architecture.

Replaces the sequential AutoAgent pipeline with a concurrent, DAG-driven
approach where four specialized domain agents collaborate in parallel:

  ArchitectAgent  → produces a TaskDAG
  DeveloperAgent  → pool of N, runs in parallel per file
  DevOpsAgent     → activates after all DEVELOPER nodes complete
  AuditorAgent    → JIT scanning via EventPublisher (+ final batch pass)

Activation:
    Selected via ``config.get("use_domain_agents", False)``, or by calling
    ``DomainAgentOrchestrator.run()`` directly.

Backward compatibility:
    This class does NOT modify AutoAgent or any existing phase.
    Both entry points share the same DI container resources.

Usage::

    orchestrator = container.domain_agents.domain_agent_orchestrator()
    project_path = await orchestrator.run(
        project_description="Build a REST API…",
        project_name="myapi",
        pool_size=3,
    )
"""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agents.domain_agents.architect_agent import ArchitectAgent
from backend.agents.domain_agents.auditor_agent import AuditorAgent
from backend.agents.domain_agents.developer_agent import DeveloperAgent
from backend.agents.domain_agents.devops_agent import DevOpsAgent
from backend.agents.orchestrators.blackboard import Blackboard
from backend.agents.orchestrators.self_healing_loop import SelfHealingLoop
from backend.agents.orchestrators.task_dag import AgentType, TaskDAG, TaskNode, TaskStatus
from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher
from backend.utils.core.io.locked_file_manager import LockedFileManager
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher


class DomainAgentOrchestrator:
    """
    Top-level orchestrator for the Agent-per-Domain architecture.

    All work is fully async.  The execution loop drives a DAG where tasks
    whose dependencies are satisfied are dispatched concurrently, bounded by
    an asyncio.Semaphore of size *pool_size*.

    Self-healing:
        When any task fails, ``SelfHealingLoop`` re-queues a REMEDIATION
        node so the DAG keeps running.  Independent tasks are never blocked
        by an isolated failure.
    """

    def __init__(
        self,
        architect_agent: ArchitectAgent,
        developer_agent_pool: List[DeveloperAgent],
        devops_agent: DevOpsAgent,
        auditor_agent: AuditorAgent,
        blackboard: Blackboard,
        tool_dispatcher: ToolDispatcher,
        self_healing_loop: SelfHealingLoop,
        locked_file_manager: LockedFileManager,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        generated_projects_dir: Optional[Path] = None,
    ) -> None:
        self._architect = architect_agent
        self._dev_pool = developer_agent_pool
        self._devops = devops_agent
        self._auditor = auditor_agent
        self._blackboard = blackboard
        self._tool_dispatcher = tool_dispatcher
        self._healing_loop = self_healing_loop
        self._file_manager = locked_file_manager
        self._event_publisher = event_publisher
        self._logger = logger
        self._generated_projects_dir = generated_projects_dir or Path(".ollash/generated_projects")
        self._pool_index: int = 0  # Round-robin developer pool counter

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        project_description: str,
        project_name: str,
        pool_size: int = 3,
        readme_content: str = "",
    ) -> Path:
        """Execute the full Agent-per-Domain pipeline.

        Args:
            project_description: Natural language project request.
            project_name: Short identifier used for the output directory.
            pool_size: Maximum number of concurrent tasks in the DAG loop.
            readme_content: Optional pre-generated README (used as context).

        Returns:
            Path to the generated project directory.
        """
        self._logger.info(f"[DomainOrchestrator] Starting project '{project_name}'")
        self._event_publisher.publish(
            "domain_orchestration_started",
            project_name=project_name,
            pool_size=pool_size,
        )

        # 1 — Initialise shared Blackboard keys
        project_root = await self._initialize(
            project_description, project_name, readme_content
        )

        # 2 — Architect produces the TaskDAG
        dag = await self._architect.plan_dag(
            project_description=project_description,
            project_name=project_name,
            blackboard=self._blackboard,
        )

        # 3 — Wire AuditorAgent to the live event loop
        self._auditor.set_blackboard(self._blackboard)
        try:
            self._auditor.set_event_loop(asyncio.get_running_loop())
        except RuntimeError:
            pass

        # 4 — Execute DAG
        await self._execution_loop(dag, pool_size)

        # 5 — Finalise: write all files to disk
        self._finalize(project_root, dag)

        self._event_publisher.publish(
            "domain_orchestration_completed",
            project_name=project_name,
            project_root=str(project_root),
            stats=dag.stats(),
        )
        self._logger.info(
            f"[DomainOrchestrator] Project '{project_name}' complete. "
            f"Stats: {dag.stats()}"
        )
        return project_root

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def _initialize(
        self,
        project_description: str,
        project_name: str,
        readme_content: str,
    ) -> Path:
        """Create project root directory and prime the Blackboard."""
        project_root = self._generated_projects_dir / project_name
        project_root.mkdir(parents=True, exist_ok=True)

        await self._blackboard.write("project_description", project_description, "orchestrator")
        await self._blackboard.write("project_name", project_name, "orchestrator")
        await self._blackboard.write("readme_content", readme_content, "orchestrator")
        await self._blackboard.write("generated_files", {}, "orchestrator")
        await self._blackboard.write("codebase_stable", False, "orchestrator")
        await self._blackboard.write("project_root", str(project_root), "orchestrator")

        self._logger.debug(f"[DomainOrchestrator] project_root: {project_root}")
        return project_root

    # ------------------------------------------------------------------
    # DAG execution loop
    # ------------------------------------------------------------------

    async def _execution_loop(self, dag: TaskDAG, pool_size: int) -> None:
        """Drive the DAG by continuously dispatching ready tasks.

        Uses a Semaphore to cap concurrency at *pool_size*.
        Loops until every node is COMPLETED or FAILED.
        """
        semaphore = asyncio.Semaphore(pool_size)
        in_flight: set = set()

        while not dag.is_complete():
            ready = dag.get_ready_tasks()

            for node in ready:
                if node.id in in_flight:
                    continue
                in_flight.add(node.id)
                await dag.mark_in_progress(node.id)

                task = asyncio.create_task(
                    self._dispatch_with_semaphore(node, dag, semaphore)
                )
                task.add_done_callback(lambda t, nid=node.id: in_flight.discard(nid))

            if not ready and not in_flight:
                # No progress possible (all remaining nodes are waiting for
                # in-flight tasks or have failed deps)
                await asyncio.sleep(0.1)
            else:
                await asyncio.sleep(0.05)

        # Allow final background audit tasks to complete
        await asyncio.sleep(0.2)

    async def _dispatch_with_semaphore(
        self,
        node: TaskNode,
        dag: TaskDAG,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Acquire semaphore slot, dispatch task, release on completion."""
        async with semaphore:
            await self._dispatch_task(node, dag)

    async def _dispatch_task(self, node: TaskNode, dag: TaskDAG) -> None:
        """Route a task to its domain agent and handle success / failure."""
        project_description: str = self._blackboard.read("project_description", "")
        readme: str = self._blackboard.read("readme_content", "")
        ctx_snapshot: Dict[str, Any] = copy.deepcopy(self._blackboard.snapshot())

        try:
            result = await self._route_to_agent(node)
            await dag.mark_complete(node.id, result)

            # Mark codebase as stable when all DEVELOPER nodes are done
            if node.agent_type == AgentType.DEVELOPER:
                self._check_and_set_stable(dag)

        except Exception as exc:
            self._logger.error(
                f"[DomainOrchestrator] Task '{node.id}' failed: {exc}"
            )
            node.error = str(exc)
            await dag.mark_failed(node.id, str(exc))

            # Self-healing: re-queue remediation
            try:
                await self._healing_loop.handle_failure(
                    failed_node=node,
                    dag=dag,
                    blackboard=self._blackboard,
                    project_description=project_description,
                    readme_content=readme,
                    phase_context_snapshot=ctx_snapshot,
                )
            except Exception as heal_exc:
                self._logger.error(
                    f"[DomainOrchestrator] SelfHealingLoop failed for '{node.id}': {heal_exc}"
                )

    async def _route_to_agent(self, node: TaskNode) -> Any:
        """Dispatch a node to the correct domain agent."""
        if node.agent_type == AgentType.ARCHITECT:
            return await self._architect.run(node, self._blackboard)

        if node.agent_type == AgentType.DEVELOPER:
            agent = self._get_next_developer()
            return await agent.run(node, self._blackboard)

        if node.agent_type == AgentType.DEVOPS:
            return await self._devops.run(node, self._blackboard)

        if node.agent_type == AgentType.AUDITOR:
            return await self._auditor.run(node, self._blackboard)

        raise ValueError(f"Unknown agent type: {node.agent_type}")

    # ------------------------------------------------------------------
    # Developer pool
    # ------------------------------------------------------------------

    def _get_next_developer(self) -> DeveloperAgent:
        """Round-robin selection from the developer pool."""
        if not self._dev_pool:
            raise RuntimeError("Developer agent pool is empty.")
        agent = self._dev_pool[self._pool_index % len(self._dev_pool)]
        self._pool_index += 1
        return agent

    # ------------------------------------------------------------------
    # Stability gate
    # ------------------------------------------------------------------

    def _check_and_set_stable(self, dag: TaskDAG) -> None:
        """Set codebase_stable=True when all DEVELOPER nodes have completed."""
        all_dev_done = all(
            n.status == TaskStatus.COMPLETED
            for n in dag.all_nodes()
            if n.agent_type == AgentType.DEVELOPER
        )
        if all_dev_done and not self._blackboard.read("codebase_stable"):
            asyncio.create_task(
                self._blackboard.write("codebase_stable", True, "orchestrator")
            )
            self._logger.info(
                "[DomainOrchestrator] All DEVELOPER tasks done — codebase_stable=True"
            )

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------

    def _finalize(self, project_root: Path, dag: TaskDAG) -> None:
        """Write all Blackboard-stored files to disk and log summary."""
        # Write generated source files
        generated = self._blackboard.get_all_generated_files()
        infra = self._blackboard.read_prefix("infra_files/")
        all_files: Dict[str, str] = {}
        all_files.update(generated)
        all_files.update(
            {k[len("infra_files/"):]: v for k, v in infra.items()}
        )

        for rel_path, content in all_files.items():
            if not isinstance(content, str):
                continue
            try:
                dest = project_root / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                self._file_manager.write_file(str(dest), content)
            except Exception as exc:
                self._logger.error(
                    f"[DomainOrchestrator] Failed to write '{rel_path}': {exc}"
                )

        stats = dag.stats()
        self._logger.info(
            f"[DomainOrchestrator] Finalised — "
            f"{stats.get('COMPLETED', 0)} tasks completed, "
            f"{stats.get('FAILED', 0)} failed, "
            f"{len(all_files)} files written to {project_root}"
        )
