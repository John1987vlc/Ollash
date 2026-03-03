"""
Self-Healing Loop for the Domain Agent Orchestrator.

When a TaskNode fails, this module:
1. Records the error pattern in the ErrorKnowledgeBase for long-term learning.
2. Calls ContingencyPlanner to produce a recovery plan.
3. Creates a REMEDIATION TaskNode and re-queues it in the DAG.
4. Publishes a ``task_remediation_queued`` event.

Independent tasks in the DAG continue executing while the remediation is
prepared and re-queued, ensuring no global pipeline stall.

A ``handle_validation_failure`` entry point handles the narrower case where a
DeveloperAgent's generated file fails FileValidator checks — allowing sub-agent
correction on that specific file immediately.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from backend.utils.core.memory.error_knowledge_base import ErrorKnowledgeBase
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.domains.auto_generation.contingency_planner import ContingencyPlanner

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskDAG, TaskNode


@dataclass
class RemediationResult:
    """Outcome of a self-healing attempt."""

    success: bool
    remediation_task_id: str
    plan: Dict[str, Any]
    error: Optional[str] = None


class SelfHealingLoop:
    """
    Self-healing mechanism that re-queues failed tasks with enriched context.

    Attributes:
        max_retries: Maximum number of remediation attempts per task before
                     marking it as permanently failed.
    """

    def __init__(
        self,
        error_knowledge_base: ErrorKnowledgeBase,
        contingency_planner: ContingencyPlanner,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        max_retries: int = 2,
    ) -> None:
        self._ekb = error_knowledge_base
        self._cp = contingency_planner
        self._event_publisher = event_publisher
        self._logger = logger
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    async def handle_failure(
        self,
        failed_node: "TaskNode",
        dag: "TaskDAG",
        blackboard: "Blackboard",
        project_description: str,
        readme_content: str,
        phase_context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> RemediationResult:
        """Handle a failed DAG task with error recording and re-queuing.

        Args:
            failed_node: The TaskNode that raised an exception.
            dag: The live TaskDAG to add the remediation node to.
            blackboard: The shared Blackboard (used for additional context).
            project_description: Original user project request.
            readme_content: Project README (used by ContingencyPlanner).
            phase_context_snapshot: Optional deep-copy of context state
                                    (prevents contaminating live state).

        Returns:
            RemediationResult indicating success/failure and the new task id.
        """
        node_id = failed_node.id
        error_msg = failed_node.error or "Unknown error"

        # Guard: don't retry beyond max_retries
        if failed_node.retry_count >= self.max_retries:
            self._logger.warning(
                f"[SelfHealingLoop] Task '{node_id}' exhausted max retries "
                f"({self.max_retries}). Marking as permanently failed."
            )
            await self._event_publisher.publish(
                "task_permanently_failed",
                task_id=node_id,
                retry_count=failed_node.retry_count,
                error=error_msg,
            )
            return RemediationResult(
                success=False,
                remediation_task_id="",
                plan={},
                error=f"Max retries ({self.max_retries}) exceeded",
            )

        self._logger.info(
            f"[SelfHealingLoop] Handling failure for '{node_id}' "
            f"(attempt {failed_node.retry_count + 1}/{self.max_retries})"
        )

        # 1. Record error pattern
        file_content = str(phase_context_snapshot or {})[:500] if phase_context_snapshot else ""
        pattern_id = self._ekb.record_error(
            file_path=node_id,
            error_type=self._classify_error(error_msg),
            error_message=error_msg,
            file_content=file_content,
            context=f"DomainAgent:{failed_node.agent_type.value}",
            solution=None,
        )
        self._logger.debug(
f"[SelfHealingLoop] Error pattern recorded: {pattern_id}")

        # 2. Generate contingency plan — prepend real sandbox errors if available
        issues = self._build_issues_from_node(failed_node)
        sandbox_errors = blackboard.read(f"sandbox_errors/{failed_node.id}")
        if sandbox_errors:
            # Inject real compiler/linter traceback into the first issue
            issues[0]["sandbox_traceback"] = sandbox_errors
            self._logger.info(f"[SelfHealingLoop] Injecting sandbox errors for '{failed_node.id}'")
        plan: Dict[str, Any] = {}
        try:
            plan = await self._cp.generate_contingency_plan(
                issues=issues,
                project_description=project_description,
                readme=readme_content,
            )
        except Exception as cp_exc:
            self._logger.error(f"[SelfHealingLoop] ContingencyPlanner failed: {cp_exc}")
            plan = {"actions": []}

        # 3. Retrieve prevention tips from knowledge base
        prevention_tips = self._get_prevention_tips(node_id)

        # 4. Create remediation TaskNode
        remediation_node = self._create_remediation_node(
            original_node=failed_node,
            plan=plan,
            pattern_id=pattern_id,
            prevention_tips=prevention_tips,
        )

        # 5. Add to DAG
        try:
            dag.add_task(remediation_node)
        except ValueError:
            # Node id already exists (edge case with duplicate IDs)
            remediation_node.id = f"{remediation_node.id}_{remediation_node.retry_count}"
            dag.add_task(remediation_node)

        # 6. Publish event
        await self._event_publisher.publish(
            "task_remediation_queued",
            original_task_id=node_id,
            remediation_task_id=remediation_node.id,
            retry_count=remediation_node.retry_count,
            pattern_id=pattern_id,
        )

        self._logger.info(f"[SelfHealingLoop] Remediation task '{remediation_node.id}' queued.")

        return RemediationResult(
            success=True,
            remediation_task_id=remediation_node.id,
            plan=plan,
        )

    async def handle_validation_failure(
        self,
        file_path: str,
        content: str,
        error: str,
        dag: "TaskDAG",
        blackboard: "Blackboard",
        project_description: str = "",
        readme_content: str = "",
    ) -> RemediationResult:
        """Handle a FileValidator failure for a specific generated file.

        Creates an isolated remediation task for just that file without
        stalling any other in-progress generation tasks.
        """
        from backend.agents.orchestrators.task_dag import AgentType, TaskNode

        self._logger.info(f"[SelfHealingLoop] FileValidator failure on '{file_path}': {error[:80]}")

        pattern_id = self._ekb.record_error(
            file_path=file_path,
            error_type="validation",
            error_message=error,
            file_content=content[:500],
            context="FileValidator",
            solution=None,
        )

        prevention_tips = self._get_prevention_tips(file_path)

        remediation_id = f"validate_fix_{Path(file_path).name}"
        try:
            remediation_node = TaskNode(
                id=remediation_id,
                agent_type=AgentType.DEVELOPER,
                task_data={
                    "file_path": file_path,
                    "is_remediation": True,
                    "is_validation_fix": True,
                    "original_content": content,
                    "validation_error": error,
                    "prevention_tips": prevention_tips,
                    "remediation_actions": [{"type": "fix_syntax", "path": file_path, "error": error}],
                },
                dependencies=[],
                retry_count=1,
            )
            dag.add_task(remediation_node)
        except ValueError:
            pass  # Already queued

        await self._event_publisher.publish(
            "task_remediation_queued",
            original_task_id=file_path,
            remediation_task_id=remediation_id,
            retry_count=1,
            pattern_id=pattern_id,
            trigger="validation_failure",
        )

        return RemediationResult(
            success=True,
            remediation_task_id=remediation_id,
            plan={"actions": [{"type": "fix_validation", "path": file_path}]},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_issues_from_node(self, node: "TaskNode") -> List[Dict[str, Any]]:
        """Convert a failed TaskNode into ContingencyPlanner issues format."""
        return [
            {
                "description": f"Failed to execute task '{node.id}': {node.error or 'Unknown'}",
                "file_path": node.id,
                "error_type": self._classify_error(node.error or ""),
                "agent_type": node.agent_type.value,
            }
        ]

    def _classify_error(self, error_msg: str) -> str:
        """Infer a high-level error category from the error message."""
        lowered = error_msg.lower()
        if any(k in lowered for k in ("syntaxerror", "syntax error", "invalid syntax")):
            return "syntax"
        if any(k in lowered for k in ("importerror", "modulenotfounderror", "no module")):
            return "import"
        if any(k in lowered for k in ("nameerror", "attributeerror", "typeerror")):
            return "logic"
        if any(k in lowered for k in ("timeout", "connection", "network")):
            return "network"
        if any(k in lowered for k in ("filenotfounderror", "permissionerror")):
            return "filesystem"
        return "generation"

    def _get_prevention_tips(self, file_path: str) -> str:
        """Retrieve prevention tips from ErrorKnowledgeBase if available."""
        try:
            patterns = self._ekb.get_patterns_for_file(file_path)
            if patterns:
                tips = [p.prevention_tip for p in patterns if p.prevention_tip]
                return "\n".join(f"- {t}" for t in tips[:3])
        except AttributeError:
            pass
        return ""

    def _create_remediation_node(
        self,
        original_node: "TaskNode",
        plan: Dict[str, Any],
        pattern_id: str,
        prevention_tips: str,
    ) -> "TaskNode":
        """Build a REMEDIATION TaskNode enriched with contingency actions."""
        from backend.agents.orchestrators.task_dag import TaskNode

        remediation_id = f"remediate_{original_node.id}_{original_node.retry_count + 1}"
        enriched_data = copy.deepcopy(original_node.task_data)
        enriched_data.update(
            {
                "is_remediation": True,
                "original_error": original_node.error or "",
                "remediation_actions": plan.get("actions", []),
                "prevention_tips": prevention_tips,
                "known_pattern_id": pattern_id,
            }
        )

        return TaskNode(
            id=remediation_id,
            agent_type=original_node.agent_type,
            task_data=enriched_data,
            dependencies=[],  # No DAG blocking — retries immediately
            retry_count=original_node.retry_count + 1,
        )
