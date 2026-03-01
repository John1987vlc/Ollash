"""
DevOps Agent — Infrastructure-as-Code generation.

Responsibilities:
- Activate ONLY when ``blackboard['codebase_stable'] == True``.
- Optionally assess codebase stability via LLM before generating infra.
- Generate Dockerfile, docker-compose.yml, CI/CD workflows, etc.
- Heal CI/CD failures if ``blackboard['ci_failures']`` is set.
- Write generated infra files back to Blackboard and to disk.

The stability gate prevents running expensive infrastructure generation on an
incomplete codebase.  The orchestrator sets ``codebase_stable=True`` after all
DEVELOPER nodes have completed.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, TYPE_CHECKING

from backend.agents.domain_agents.base_domain_agent import BaseDomainAgent
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.cicd_healer import CICDHealer
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.domains.auto_generation.infra_generator import InfraGenerator

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskNode
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher


class DevOpsAgent(BaseDomainAgent):
    """
    DEVOPS domain agent.

    Output keys written to Blackboard:
        ``infra_files/{rel_path}``  — Generated infrastructure file contents
    """

    REQUIRED_TOOLS: List[str] = ["infra_generator", "cicd_healer"]
    agent_id: str = "devops"

    def __init__(
        self,
        infra_generator: InfraGenerator,
        cicd_healer: CICDHealer,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
    ) -> None:
        super().__init__(event_publisher, logger, tool_dispatcher)
        self._infra_gen = infra_generator
        self._cicd_healer = cicd_healer

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        node: "TaskNode",
        blackboard: "Blackboard",
    ) -> Dict[str, str]:
        """Generate infrastructure files for the project.

        Returns:
            ``{rel_path: content}`` mapping of generated infra files.
            Returns an empty dict if the codebase_stable gate is not set.
        """
        is_stable: bool = blackboard.read("codebase_stable", False)
        if not is_stable:
            self._log_warning(
                "Stability gate not set — skipping infrastructure generation. "
                "Set 'codebase_stable=True' in the Blackboard to activate DevOps."
            )
            return {}

        project_name: str = blackboard.read("project_name", "project")
        project_description: str = blackboard.read("project_description", "")
        generated_files: Dict[str, str] = blackboard.get_all_generated_files()

        self._log_info(f"Generating infrastructure for '{project_name}' ({len(generated_files)} source files)")
        self._publish_event("devops_started", project=project_name)

        infra_files: Dict[str, str] = {}

        # 1 — Generate infrastructure files
        try:
            infra_files = await self._generate_infra(
                project_name=project_name,
                project_description=project_description,
                generated_files=generated_files,
            )
        except Exception as exc:
            self._log_error(f"InfraGenerator failed: {exc}")

        # 2 — Heal CI/CD failures if any are registered in the Blackboard
        ci_failures: Optional[list] = blackboard.read("ci_failures")
        if ci_failures:
            healed = await self._heal_ci_failures(ci_failures, project_name)
            infra_files.update(healed)

        # 3 — Write to Blackboard
        for rel_path, content in infra_files.items():
            await blackboard.write(f"infra_files/{rel_path}", content, self.agent_id)

        self._publish_event(
            "infra_generated",
            project=project_name,
            file_count=len(infra_files),
            files=list(infra_files.keys()),
        )
        self._log_info(f"Infrastructure generation complete: {len(infra_files)} files.")
        return infra_files

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _generate_infra(
        self,
        project_name: str,
        project_description: str,
        generated_files: Dict[str, str],
    ) -> Dict[str, str]:
        """Delegate to InfraGenerator (sync) wrapped in executor."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._infra_gen.generate(
                    project_name=project_name,
                    project_description=project_description,
                    generated_files=generated_files,
                ),
            )
            if isinstance(result, dict):
                return result
        except TypeError:
            # Some InfraGenerator signatures may differ
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: self._infra_gen.generate(
                        project_description=project_description,
                        generated_files=generated_files,
                    ),
                )
                if isinstance(result, dict):
                    return result
            except Exception as exc2:
                self._log_error(f"InfraGenerator fallback failed: {exc2}")
        except Exception as exc:
            self._log_error(f"InfraGenerator error: {exc}")

        return {}

    async def _heal_ci_failures(
        self,
        ci_failures: list,
        project_name: str,
    ) -> Dict[str, str]:
        """Call CICDHealer for each registered CI failure and collect fix files."""
        healed_files: Dict[str, str] = {}
        loop = asyncio.get_event_loop()
        for failure in ci_failures:
            workflow_log: str = failure.get("log", "")
            workflow_name: str = failure.get("name", "unknown")
            if not workflow_log:
                continue
            try:
                analysis = await loop.run_in_executor(
                    None,
                    lambda: self._cicd_healer.analyze_failure(
                        workflow_log=workflow_log,
                        workflow_name=workflow_name,
                    ),
                )
                if analysis and hasattr(analysis, "suggested_fixes"):
                    for fix_path, fix_content in analysis.suggested_fixes.items():
                        healed_files[fix_path] = fix_content
                        self._log_info(f"CICDHealer fix applied: {fix_path}")
            except Exception as exc:
                self._log_error(f"CICDHealer failed for '{workflow_name}': {exc}")

        return healed_files
