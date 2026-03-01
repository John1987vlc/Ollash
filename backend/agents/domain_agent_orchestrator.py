"""
Domain Agent Orchestrator — Entry Point for Agent-per-Domain Architecture.

Replaces the sequential AutoAgent pipeline with a concurrent, DAG-driven
approach where four specialized domain agents collaborate in parallel:

  ArchitectAgent  → produces a TaskDAG
  DeveloperAgent  → pool of N, runs in parallel per file
  DevOpsAgent     → activates after all DEVELOPER nodes complete
  AuditorAgent    → JIT scanning via EventPublisher (+ final batch pass)
  DebateNodeRunner → resolves DEBATE nodes via multi-agent consensus

New capabilities (10-point evolutionary improvements):
  P1  HITL  — nodes can pause with WAITING_FOR_USER and resume on user answer
  P2  Checkpoint — DAG state saved after every completion; resume() rebuilds
  P4  Streaming — DeveloperAgent streams chunks to Blackboard (handled by agent)
  P5  Budget   — token budget check before dispatching; circuit breaker on retries
  P6  Git      — per-file auto-commits with diff capture after finalization
  P8  Debate   — DEBATE nodes route through DebateNodeRunner
  P9  Tools    — ToolDispatcher emits tool_execution_started/completed events
  P10 Metrics  — node completion and project stats recorded in MetricsDatabase

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
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.agents.domain_agents.architect_agent import ArchitectAgent
from backend.agents.domain_agents.auditor_agent import AuditorAgent
from backend.agents.domain_agents.developer_agent import DeveloperAgent
from backend.agents.domain_agents.devops_agent import DevOpsAgent
from backend.agents.orchestrators.active_orchestrators import ActiveOrchestrators
from backend.agents.orchestrators.blackboard import Blackboard
from backend.agents.orchestrators.hitl_pause_exception import HITLPauseException
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

    HITL (Point 1):
        Agents may raise ``HITLPauseException`` to pause a node. The loop
        skips WAITING_FOR_USER nodes until ``mark_unblocked`` is called via
        the HIL API endpoint.

    Budget control (Point 5):
        If ``budget_limit_tokens`` is set, the orchestrator checks the
        cumulative token spend before each dispatch and pauses all remaining
        PENDING nodes if the limit is exceeded.

    Git commits (Point 6):
        After ``_finalize()``, ``_git_finalize()`` runs per-file git commits
        and writes ``git_manifest.json`` to the project root.
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
        git_auto_committer_factory: Optional[Callable[[Path], Any]] = None,
        checkpoint_manager: Optional[Any] = None,
        cost_analyzer: Optional[Any] = None,
        metrics_database: Optional[Any] = None,
        debate_node_runner: Optional[Any] = None,
        budget_limit_tokens: int = 500_000,
        tactical_agent: Optional[Any] = None,
        critic_agent: Optional[Any] = None,
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
        self._git_committer_factory = git_auto_committer_factory
        self._checkpoint_manager = checkpoint_manager
        self._cost_analyzer = cost_analyzer
        self._metrics_database = metrics_database
        self._debate_runner = debate_node_runner
        # F4: Granularity sub-roles
        self._tactical = tactical_agent
        self._critic = critic_agent
        self._budget_limit_tokens = budget_limit_tokens
        # asyncio.Queue is populated lazily in run() once the event loop is running.
        self._dev_queue: asyncio.Queue[DeveloperAgent] = asyncio.Queue()
        # Current live DAG (accessible for HITL unblocking via ActiveOrchestrators)
        self._current_dag: Optional[TaskDAG] = None
        self._current_project_name: str = ""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        project_description: str,
        project_name: str,
        pool_size: int = 3,
        readme_content: str = "",
        image_paths: Optional[List[Path]] = None,
    ) -> Path:
        """Execute the full Agent-per-Domain pipeline.

        Args:
            project_description: Natural language project request.
            project_name: Short identifier used for the output directory.
            pool_size: Maximum number of concurrent tasks in the DAG loop.
            readme_content: Optional pre-generated README (used as context).
            image_paths: Optional list of image Paths for multimodal context
                         (Point 7 — passed to ArchitectAgent.plan_dag).

        Returns:
            Path to the generated project directory.
        """
        self._logger.info(f"[DomainOrchestrator] Starting project '{project_name}'")
        self._current_project_name = project_name
        self._event_publisher.publish(
            "domain_orchestration_started",
            project_name=project_name,
            pool_size=pool_size,
        )

        # Register in global registry for HITL API access
        ActiveOrchestrators.register(project_name, self)

        try:
            # 1 — Initialise shared Blackboard keys
            project_root = await self._initialize(project_description, project_name, readme_content)

            # 2 — Architect produces the TaskDAG (with optional images P7)
            dag = await self._architect.plan_dag(
                project_description=project_description,
                project_name=project_name,
                blackboard=self._blackboard,
                image_paths=image_paths or [],
            )
            self._current_dag = dag

            # 3 — Populate the developer queue (must be done inside async context)
            while not self._dev_queue.empty():
                self._dev_queue.get_nowait()
            for dev in self._dev_pool:
                self._dev_queue.put_nowait(dev)

            # 4 — Wire AuditorAgent to the live event loop
            self._auditor.set_blackboard(self._blackboard)
            try:
                self._auditor.set_event_loop(asyncio.get_running_loop())
            except RuntimeError:
                pass

            # 5 — Execute DAG
            await self._execution_loop(dag, pool_size)

            # 6 — Finalise: write all files to disk
            all_files = self._finalize(project_root, dag)

            # 7 — Git auto-commit (Point 6, best-effort)
            manifest = await self._git_finalize(project_root, dag, project_name, all_files)

            # 8 — Record project-level metrics (Point 10)
            self._record_project_metrics(project_name, dag, len(all_files))

            git_committed = manifest.repo_initialised if manifest else False
            self._event_publisher.publish(
                "domain_orchestration_completed",
                project_name=project_name,
                project_root=str(project_root),
                stats=dag.stats(),
                git_committed=git_committed,
            )
            self._logger.info(f"[DomainOrchestrator] Project '{project_name}' complete. Stats: {dag.stats()}")
            return project_root

        finally:
            ActiveOrchestrators.deregister(project_name)

    # ------------------------------------------------------------------
    # Public: expose current DAG for HITL API
    # ------------------------------------------------------------------

    def get_dag(self) -> Optional[TaskDAG]:
        """Return the currently-running TaskDAG (for HITL blueprint access)."""
        return self._current_dag

    # ------------------------------------------------------------------
    # Public: resume from checkpoint (Point 2)
    # ------------------------------------------------------------------

    async def resume(self, project_name: str) -> Optional[Path]:
        """Resume a paused/interrupted project from its latest DAG checkpoint.

        Loads the serialised DAG, skips COMPLETED nodes, and re-enters the
        execution loop with PENDING/FAILED nodes only.

        Args:
            project_name: The project to resume.

        Returns:
            Path to the project root, or None if no checkpoint exists.
        """
        if self._checkpoint_manager is None:
            self._logger.warning("[DomainOrchestrator] No checkpoint manager — cannot resume")
            return None

        data = self._checkpoint_manager.load_dag(project_name)
        if data is None:
            self._logger.warning(f"[DomainOrchestrator] No DAG checkpoint for '{project_name}'")
            return None

        dag = TaskDAG.from_dict(data["dag"])
        bb_data: Dict[str, Any] = data.get("blackboard", {})

        # Restore Blackboard from snapshot (best-effort)
        for key, value in bb_data.items():
            await self._blackboard.write(key, value, "checkpoint_restore")

        self._current_dag = dag
        self._current_project_name = project_name
        project_root = Path(bb_data.get("project_root", str(self._generated_projects_dir / project_name)))

        # Reset FAILED nodes back to PENDING so they can be retried
        for node in dag.all_nodes():
            if node.status == TaskStatus.FAILED:
                node.status = TaskStatus.PENDING

        pool_size = int(bb_data.get("pool_size", 3))

        ActiveOrchestrators.register(project_name, self)
        try:
            self._auditor.set_blackboard(self._blackboard)
            try:
                self._auditor.set_event_loop(asyncio.get_running_loop())
            except RuntimeError:
                pass

            while not self._dev_queue.empty():
                self._dev_queue.get_nowait()
            for dev in self._dev_pool:
                self._dev_queue.put_nowait(dev)

            self._event_publisher.publish(
                "domain_orchestration_resumed",
                project_name=project_name,
                completed=dag.stats().get("COMPLETED", 0),
                total=len(dag.all_nodes()),
            )

            await self._execution_loop(dag, pool_size)
            all_files = self._finalize(project_root, dag)
            await self._git_finalize(project_root, dag, project_name, all_files)
            return project_root
        finally:
            ActiveOrchestrators.deregister(project_name)

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
        Loops until every node is COMPLETED or FAILED (or WAITING_FOR_USER
        with no other tasks in flight — which signals a full HITL pause).
        """
        semaphore = asyncio.Semaphore(pool_size)
        in_flight: set = set()

        while not dag.is_complete():
            ready = await dag.get_ready_tasks()

            for node in ready:
                if node.id in in_flight:
                    continue

                # P5 — Budget check before dispatching
                if self._budget_exceeded():
                    await self._apply_budget_pause(dag)
                    break

                in_flight.add(node.id)
                await dag.mark_in_progress(node.id)

                task = asyncio.create_task(self._dispatch_with_semaphore(node, dag, semaphore))
                task.add_done_callback(lambda t, nid=node.id: in_flight.discard(nid))

            # P1 — Re-queue nodes that have been answered by the user
            for node in dag.get_waiting_nodes():
                if node.hitl_answer is not None:
                    await dag.mark_unblocked(node.id, node.hitl_answer)

            if not ready and not in_flight:
                # No progress possible — check if stuck on WAITING_FOR_USER
                waiting = dag.get_waiting_nodes()
                if waiting:
                    await asyncio.sleep(0.5)  # Poll for user answer
                    continue
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
        node_start_time = time.monotonic()

        # Notify UI that this task is starting
        self._event_publisher.publish(
            "task_status_changed",
            task_id=node.id,
            status=TaskStatus.IN_PROGRESS.value,
            agent_type=node.agent_type.value,
        )

        # F5: Inject context notes from completed dependency nodes
        dep_notes = [
            self._blackboard.read(f"context_notes/{dep}")
            for dep in node.dependencies
            if self._blackboard.read(f"context_notes/{dep}")
        ]
        if dep_notes:
            node.task_data["previous_context"] = "\n---\n".join(dep_notes)

        try:
            result = await self._route_to_agent(node)
            await dag.mark_complete(node.id, result)

            # F5: Persist the agent's context note to Blackboard for downstream tasks
            if isinstance(result, dict) and result.get("context_note"):
                await self._blackboard.write(
                    f"context_notes/{node.id}", result["context_note"], node.id
                )
                node.context_note = result["context_note"]

            duration_ms = int((time.monotonic() - node_start_time) * 1000)

            self._event_publisher.publish(
                "task_status_changed",
                task_id=node.id,
                status=TaskStatus.COMPLETED.value,
                agent_type=node.agent_type.value,
                duration_ms=duration_ms,
            )

            # Mark codebase as stable when all DEVELOPER nodes are done
            if node.agent_type == AgentType.DEVELOPER:
                self._check_and_set_stable(dag)

            # P2 — Save checkpoint after each completion (fire-and-forget)
            asyncio.create_task(self._save_checkpoint(dag))

            # P10 — Record node metrics
            self._record_node_metrics(node, duration_ms)

        except HITLPauseException as hitl_exc:
            # P1 — Agent requested human input: pause node, keep DAG running
            self._logger.info(f"[DomainOrchestrator] HITL pause on '{node.id}': {hitl_exc.question}")
            await dag.mark_waiting(node.id, hitl_exc.question)
            self._event_publisher.publish(
                "hitl_requested",
                task_id=node.id,
                agent_type=node.agent_type.value,
                question=hitl_exc.question,
                context=hitl_exc.context,
            )

        except Exception as exc:
            self._logger.error(f"[DomainOrchestrator] Task '{node.id}' failed: {exc}")
            node.error = str(exc)
            await dag.mark_failed(node.id, str(exc))

            self._event_publisher.publish(
                "task_status_changed",
                task_id=node.id,
                status=TaskStatus.FAILED.value,
                agent_type=node.agent_type.value,
                error=str(exc),
            )

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
                self._logger.error(f"[DomainOrchestrator] SelfHealingLoop failed for '{node.id}': {heal_exc}")

    async def _route_to_agent(self, node: TaskNode, timeout: float = 300.0) -> Any:
        """Dispatch a node to the correct domain agent with a per-task timeout."""
        if node.agent_type == AgentType.ARCHITECT:
            try:
                return await asyncio.wait_for(self._architect.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"ARCHITECT task '{node.id}' timed out after {timeout}s")

        if node.agent_type == AgentType.DEVELOPER:
            agent = await self._checkout_developer()
            try:
                return await asyncio.wait_for(agent.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"DEVELOPER task '{node.id}' timed out after {timeout}s")
            finally:
                self._return_developer(agent)

        if node.agent_type == AgentType.DEVOPS:
            try:
                return await asyncio.wait_for(self._devops.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"DEVOPS task '{node.id}' timed out after {timeout}s")

        if node.agent_type == AgentType.AUDITOR:
            try:
                return await asyncio.wait_for(self._auditor.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"AUDITOR task '{node.id}' timed out after {timeout}s")

        if node.agent_type == AgentType.DEBATE:
            # P8 — Route through DebateNodeRunner
            if self._debate_runner is None:
                raise RuntimeError("DEBATE node requires a DebateNodeRunner (not configured)")
            try:
                return await asyncio.wait_for(self._debate_runner.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"DEBATE task '{node.id}' timed out after {timeout}s")

        # F4: Granularity sub-roles
        if node.agent_type == AgentType.TACTICAL:
            if self._tactical is None:
                raise RuntimeError("TACTICAL node requires a TacticalAgent (not configured)")
            try:
                return await asyncio.wait_for(self._tactical.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"TACTICAL task '{node.id}' timed out after {timeout}s")

        if node.agent_type == AgentType.CRITIC:
            if self._critic is None:
                raise RuntimeError("CRITIC node requires a CriticAgent (not configured)")
            try:
                return await asyncio.wait_for(self._critic.run(node, self._blackboard), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"CRITIC task '{node.id}' timed out after {timeout}s")

        raise ValueError(f"Unknown agent type: {node.agent_type}")

    # ------------------------------------------------------------------
    # Developer queue helpers
    # ------------------------------------------------------------------

    async def _checkout_developer(self) -> DeveloperAgent:
        """Claim the next available developer agent from the queue."""
        return await self._dev_queue.get()

    def _return_developer(self, agent: DeveloperAgent) -> None:
        """Return a developer agent to the available pool."""
        self._dev_queue.put_nowait(agent)

    # ------------------------------------------------------------------
    # Stability gate
    # ------------------------------------------------------------------

    def _check_and_set_stable(self, dag: TaskDAG) -> None:
        """Set codebase_stable=True when all DEVELOPER nodes have completed."""
        all_dev_done = all(
            n.status == TaskStatus.COMPLETED for n in dag.all_nodes() if n.agent_type == AgentType.DEVELOPER
        )
        if all_dev_done and not self._blackboard.read("codebase_stable"):
            asyncio.create_task(self._blackboard.write("codebase_stable", True, "orchestrator"))
            self._logger.info("[DomainOrchestrator] All DEVELOPER tasks done — codebase_stable=True")

    # ------------------------------------------------------------------
    # Budget control (Point 5)
    # ------------------------------------------------------------------

    def _budget_exceeded(self) -> bool:
        """Return True if total token spend exceeds the configured limit."""
        if self._cost_analyzer is None or self._budget_limit_tokens <= 0:
            return False
        total = self._cost_analyzer.get_total_tokens(self._current_project_name)
        return total >= self._budget_limit_tokens

    async def _apply_budget_pause(self, dag: TaskDAG) -> None:
        """Pause all PENDING nodes as WAITING_FOR_USER due to budget limit."""
        question = f"Budget limit of {self._budget_limit_tokens:,} tokens reached. Continue generating?"
        for node in dag.all_nodes():
            if node.status == TaskStatus.PENDING:
                await dag.mark_waiting(node.id, question)
        self._event_publisher.publish(
            "budget_exceeded",
            project_name=self._current_project_name,
            limit=self._budget_limit_tokens,
        )
        self._logger.warning(f"[DomainOrchestrator] Budget limit ({self._budget_limit_tokens:,} tokens) reached")

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------

    def _finalize(self, project_root: Path, dag: TaskDAG) -> Dict[str, str]:
        """Write all Blackboard-stored files to disk and log summary."""
        generated = self._blackboard.get_all_generated_files()
        infra = self._blackboard.read_prefix("infra_files/")
        all_files: Dict[str, str] = {}
        all_files.update(generated)
        all_files.update({k[len("infra_files/") :]: v for k, v in infra.items()})

        for rel_path, content in all_files.items():
            if not isinstance(content, str):
                continue
            try:
                dest = project_root / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                self._file_manager.write_file(str(dest), content)
            except Exception as exc:
                self._logger.error(f"[DomainOrchestrator] Failed to write '{rel_path}': {exc}")

        stats = dag.stats()
        self._logger.info(
            f"[DomainOrchestrator] Finalised — "
            f"{stats.get('COMPLETED', 0)} tasks completed, "
            f"{stats.get('FAILED', 0)} failed, "
            f"{len(all_files)} files written to {project_root}"
        )
        return all_files

    # ------------------------------------------------------------------
    # Git finalization (Point 6)
    # ------------------------------------------------------------------

    async def _git_finalize(
        self,
        project_root: Path,
        dag: TaskDAG,
        project_name: str,
        all_files: Dict[str, str],
    ) -> Optional[Any]:
        """Create per-file git commits in topological order, write git_manifest.json.

        Runs blocking git operations via asyncio.to_thread so the event loop
        is never blocked.  Returns a GitManifest (or None on error).
        """
        if self._git_committer_factory is None:
            return None

        try:
            # Build ordered file list from topological DAG sort
            try:
                topo_nodes = dag.topological_sort()
            except Exception:
                topo_nodes = dag.all_nodes()

            ordered_files: List[Dict[str, Any]] = []
            seen: set = set()

            for node in topo_nodes:
                if node.status != TaskStatus.COMPLETED:
                    continue
                if node.agent_type == AgentType.DEVELOPER:
                    rel_path = node.task_data.get("file_path", node.id)
                    if rel_path not in seen and rel_path in all_files:
                        ordered_files.append(
                            {
                                "rel_path": rel_path,
                                "agent_type": node.agent_type.value,
                                "content": all_files.get(rel_path, ""),
                            }
                        )
                        seen.add(rel_path)
                elif node.agent_type == AgentType.DEVOPS:
                    infra = self._blackboard.read_prefix("infra_files/")
                    for key, content in infra.items():
                        rel = key[len("infra_files/") :]
                        if rel not in seen:
                            ordered_files.append(
                                {
                                    "rel_path": rel,
                                    "agent_type": node.agent_type.value,
                                    "content": content,
                                }
                            )
                            seen.add(rel)

            # Any remaining files not yet seen (infra, etc.)
            for rel_path, content in all_files.items():
                if rel_path not in seen:
                    ordered_files.append(
                        {
                            "rel_path": rel_path,
                            "agent_type": "DEVELOPER",
                            "content": content,
                        }
                    )

            committer = self._git_committer_factory(project_root)
            manifest = await asyncio.to_thread(committer.commit_all, ordered_files, project_name)

            manifest_path = project_root / "git_manifest.json"
            manifest_json = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False)
            await asyncio.to_thread(manifest_path.write_text, manifest_json, "utf-8")

            self._event_publisher.publish(
                "file_committed",
                project_name=project_name,
                project_root=str(project_root),
                total_commits=len(manifest.commits),
                repo_initialised=manifest.repo_initialised,
            )
            self._logger.info(f"[DomainOrchestrator] Git: {len(manifest.commits)} commits in {project_root}")
            return manifest

        except Exception as exc:
            self._logger.error(f"[DomainOrchestrator] _git_finalize failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Checkpoint (Point 2)
    # ------------------------------------------------------------------

    async def _save_checkpoint(self, dag: TaskDAG) -> None:
        """Serialise DAG + Blackboard to disk (called fire-and-forget)."""
        if self._checkpoint_manager is None:
            return
        try:
            dag_dict = dag.to_dict()
            bb_dict = self._blackboard.snapshot_serializable()
            await asyncio.to_thread(
                self._checkpoint_manager.save_dag,
                self._current_project_name,
                dag_dict,
                bb_dict,
            )
        except Exception as exc:
            self._logger.debug(f"[DomainOrchestrator] Checkpoint save failed: {exc}")

    # ------------------------------------------------------------------
    # Metrics (Point 10)
    # ------------------------------------------------------------------

    def _record_node_metrics(self, node: TaskNode, duration_ms: int) -> None:
        if self._metrics_database is None:
            return
        try:
            self._metrics_database.record_metric(
                category="dag",
                metric_name="node_completed",
                value={
                    "task_id": node.id,
                    "agent_type": node.agent_type.value,
                    "duration_ms": duration_ms,
                    "retry_count": node.retry_count,
                },
                tags={"project": self._current_project_name},
            )
        except Exception as exc:
            self._logger.debug(f"[DomainOrchestrator] Metrics record failed: {exc}")

    def _record_project_metrics(self, project_name: str, dag: TaskDAG, file_count: int) -> None:
        if self._metrics_database is None:
            return
        stats = dag.stats()
        total_tokens = self._cost_analyzer.get_total_tokens(project_name) if self._cost_analyzer else 0
        try:
            self._metrics_database.record_metric(
                category="dag",
                metric_name="project_completed",
                value={
                    "project_name": project_name,
                    "total_tokens": total_tokens,
                    "total_files": file_count,
                    "completed": stats.get("COMPLETED", 0),
                    "failed": stats.get("FAILED", 0),
                },
                tags={"project": project_name},
            )
        except Exception as exc:
            self._logger.debug(f"[DomainOrchestrator] Project metrics record failed: {exc}")
