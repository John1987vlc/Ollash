"""
AutoAgent Refactored with Dependency Injection
"""

import asyncio
import datetime
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dependency_injector import providers
from dependency_injector.wiring import Provide, inject

from backend.agents.auto_agent_phases.iterative_improvement_phase import IterativeImprovementPhase
from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.project_analysis_phase import ProjectAnalysisPhase
from backend.agents.auto_agent_phases.readme_generation_phase import ReadmeGenerationPhase
from backend.agents.auto_agent_phases.structure_generation_phase import StructureGenerationPhase
from backend.agents.auto_agent_phases.structure_pre_review_phase import StructurePreReviewPhase

# Core Agent and Kernel
from backend.agents.core_agent import CoreAgent
from backend.core.kernel import AgentKernel

# Agent Phases & Context
from backend.interfaces.iagent_phase import IAgentPhase
from backend.interfaces.imodel_provider import IModelProvider
from backend.utils.core.analysis.scanners.dependency_scanner import DependencyScanner
from backend.utils.core.system.execution_plan import ExecutionPlan

# Core utilities
from backend.utils.core.llm.llm_recorder import LLMRecorder
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.tools.git_pr_tool import GitPRTool


class TimedLogger:
    """
    Logger wrapper that adds [HH:MM:SS] timestamps and provides a heartbeat.
    """

    def __init__(self, logger):
        self._logger = logger
        self.last_log_time = time.time()

    def _format_msg(self, msg: str) -> str:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.last_log_time = time.time()
        return f"[{now}] {msg}"

    def info(self, msg: str, **kwargs):
        self._logger.info(self._format_msg(msg), **kwargs)

    def error(self, msg: str, **kwargs):
        self._logger.error(self._format_msg(msg), **kwargs)

    def warning(self, msg: str, **kwargs):
        self._logger.warning(self._format_msg(msg), **kwargs)

    def debug(self, msg: str, **kwargs):
        self._logger.debug(self._format_msg(msg), **kwargs)

    def heartbeat(self):
        """Logs a heartbeat if too much time has passed since last log."""
        if time.time() - self.last_log_time > 60:
            self.info("💓 HEARTBEAT - Agent is still active...")

    def __getattr__(self, name):
        return getattr(self._logger, name)


class RescuePhase:
    """A thin phase that executes a single LLM-generated rescue step (Mejora 6b).

    Created dynamically by ``AutoAgent._request_rescue_plan()`` when a pipeline
    phase fails. Logs the rescue step and publishes an ``rescue_step_executed``
    event. Does NOT write files — it records the rescue context so subsequent
    phases have a better chance of succeeding.
    """

    phase_id: str = "rescue"
    phase_label: str = "Dynamic Rescue Step"
    category: str = "rescue"

    def __init__(
        self,
        phase_context: "PhaseContext",
        step: str,
        action: str,
        step_index: int,
    ) -> None:
        self.context = phase_context
        self._step = step
        self._action = action
        self._step_index = step_index
        self.phase_id = f"rescue_{step_index}"
        self.phase_label = f"Rescue Step {step_index}: {step[:60]}"

    @property
    def phase_name(self) -> str:
        return self.phase_id

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Any,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths: List[str] = kwargs.pop("file_paths", [])
        self.context.logger.info(f"[RESCUE] Step {self._step_index}: {self._step} → Action: {self._action}")
        await self.context.event_publisher.publish(
            "rescue_step_executed",
            step=self._step,
            action=self._action,
            step_index=self._step_index,
            phase=self.phase_id,
        )
        return generated_files, initial_structure, file_paths


class AutoAgent(CoreAgent):
    """
    Orchestrates the multi-phase project creation pipeline using injected dependencies.
    Modified for Strict Sequential Flow and Dependency Management.
    """

    @inject
    def __init__(
        self,
        phase_context: PhaseContext = Provide["auto_agent_module.phase_context"],
        phases: List[IAgentPhase] = Provide["auto_agent_module.phases_list"],
        project_analysis_phase_factory: providers.Factory[ProjectAnalysisPhase] = Provide[
            "auto_agent_module.project_analysis_phase_factory"
        ],
        kernel: Optional[AgentKernel] = Provide["auto_agent_module.agent_kernel"],
        llm_manager: Optional[IModelProvider] = Provide["auto_agent_module.llm_manager"],
        llm_recorder: Optional[LLMRecorder] = Provide["core.llm_recorder"],
        dependency_scanner: Optional[DependencyScanner] = Provide["core.analysis.dependency_scanner"],
        token_tracker: Optional[TokenTracker] = Provide["core.token_tracker"],
        **kwargs,
    ):
        super().__init__(
            kernel=kernel,
            logger_name="AutoAgent",
            llm_manager=llm_manager,
            llm_recorder=llm_recorder,
            dependency_scanner=dependency_scanner,
            token_tracker=token_tracker,
        )

        self.config = self.kernel.get_full_config()
        # Wrap logger with TimedLogger
        self.logger = TimedLogger(self.logger)
        self.logger.info("AutoAgent initializing with TimedLogger.")

        if not self.llm_manager:
            raise ValueError("IModelProvider (LLMManager) must be provided to AutoAgent.")

        # --- Dependencies are now injected ---
        self.phase_context = phase_context
        self.phases = phases
        self.project_analysis_phase_factory = project_analysis_phase_factory

        # Ensure the context has a reference back to this agent instance
        self.phase_context.auto_agent = self

        # Set up the generated projects directory from the context
        self.generated_projects_dir = self.phase_context.generated_projects_dir
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)

        self.git_tool = None  # Lazy load later if needed

        self.logger.info("AutoAgent initialized with a modular phase pipeline and sequential flow.")

    def _get_or_create_loop(self):
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _build_adaptive_phases(self) -> List[IAgentPhase]:
        """Return a phase list adapted to the detected model tier.

        - full tier  (≥30B): all phases — current behaviour unchanged.
        - slim tier  (9–29B): removes DynamicDocumentationPhase, CICDHealingPhase.
        - nano tier  (≤8B):  removes ExhaustiveReviewRepairPhase,
                              DynamicDocumentationPhase, CICDHealingPhase,
                              LicenseCompliancePhase.

        Falls back to all phases on any exception so production is never blocked.

        Returns:
            Filtered list of IAgentPhase instances.
        """
        try:
            from backend.agents.auto_agent_phases.exhaustive_review_repair_phase import (
                ExhaustiveReviewRepairPhase,
            )
            from backend.agents.auto_agent_phases.dynamic_documentation_phase import (
                DynamicDocumentationPhase,
            )
            from backend.agents.auto_agent_phases.cicd_healing_phase import CICDHealingPhase
            from backend.agents.auto_agent_phases.license_compliance_phase import (
                LicenseCompliancePhase,
            )
            from backend.agents.auto_agent_phases.plan_validation_phase import PlanValidationPhase
            from backend.agents.auto_agent_phases.api_contract_phase import ApiContractPhase
            from backend.agents.auto_agent_phases.test_planning_phase import TestPlanningPhase
            from backend.agents.auto_agent_phases.component_tree_phase import ComponentTreePhase

            ctx = self.phase_context

            if bool(ctx._is_small_model()):
                from backend.agents.auto_agent_phases.clarification_phase import ClarificationPhase

                _NANO_SKIP = (
                    ExhaustiveReviewRepairPhase,
                    DynamicDocumentationPhase,
                    CICDHealingPhase,
                    LicenseCompliancePhase,
                    PlanValidationPhase,
                    ApiContractPhase,
                    TestPlanningPhase,
                    ComponentTreePhase,
                    ClarificationPhase,
                )
                filtered = [p for p in self.phases if not isinstance(p, _NANO_SKIP)]

                skipped_names = [c.__name__ for c in _NANO_SKIP]
                self.logger.info(
                    f"[AdaptivePipeline] nano tier — skipping {len(self.phases) - len(filtered)} "
                    f"heavy phases: {skipped_names}"
                )
                # F31: Enable active shadow repair by default for nano models
                ctx.feature_flags["opt6_active_shadow"] = True
                return filtered

            if ctx._is_mid_model():
                _SLIM_SKIP = (DynamicDocumentationPhase, CICDHealingPhase, PlanValidationPhase)
                filtered = [p for p in self.phases if not isinstance(p, _SLIM_SKIP)]
                self.logger.info(
                    f"[AdaptivePipeline] slim tier — skipping {len(self.phases) - len(filtered)} doc/CI phases"
                )
                return filtered

            self.logger.info("[AdaptivePipeline] full tier — all phases active")
            return list(self.phases)

        except Exception as exc:
            self.logger.warning(f"[AdaptivePipeline] Phase filter failed ({exc}), using all phases")
            return list(self.phases)

    def run(self, project_description: str, project_name: str = "new_project", **kwargs) -> Path:
        """Orchestrates the full project creation pipeline through distinct phases."""
        self.phase_context.project_description = project_description
        self.logger.info(f"[PROJECT_NAME:{project_name}] Standardizing input and starting pipeline.")

        # 1. Language Standardization
        try:
            from backend.services.language_manager import LanguageManager

            lang_manager = LanguageManager(self.llm_manager)
            loop = self._get_or_create_loop()
            project_description, _ = loop.run_until_complete(lang_manager.ensure_english_input(project_description))
        except Exception as e:
            self.logger.warning(f"Language standardization failed in AutoAgent: {e}")

        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting full generation for '{project_name}'.")

        project_root = self.generated_projects_dir / project_name
        _INFRA_DIRS = {".git", ".ollash", ".gitignore", ".env"}
        project_exists = project_root.exists() and any(p for p in project_root.iterdir() if p.name not in _INFRA_DIRS)

        if project_exists:
            self.logger.info(f"Existing project detected at {project_root}")
            (
                generated_files,
                initial_structure,
                file_paths,
            ) = self.phase_context.ingest_existing_project(project_root)
            readme_content = generated_files.get("README.md", "")

            # E6: Load last execution summary so phases can adapt to previous failures
            automation_manager = kwargs.get("automation_manager")
            task_id = kwargs.get("task_id", "")
            if automation_manager is not None and task_id:
                try:
                    last_summary = automation_manager.get_last_execution_summary(task_id)
                    self.phase_context.last_execution_summary = last_summary
                    if last_summary and last_summary.status == "error":
                        self.logger.warning(
                            f"Previous execution of task '{task_id}' failed: " + "; ".join(last_summary.errors)
                        )
                except Exception as exc:
                    self.logger.warning(f"Could not load last execution summary: {exc}")
        else:
            project_root.mkdir(parents=True, exist_ok=True)
            generated_files, initial_structure, readme_content, file_paths = (
                {},
                {},
                "",
                [],
            )

        self.phase_context.initial_exec_params = kwargs

        active_phases = self._build_adaptive_phases()
        if kwargs.get("maintenance_mode"):
            self.logger.info("🛠️ MAINTENANCE MODE ACTIVE: Skipping initial phases, focusing on audit and improvement.")
            # Skip to IterativeImprovementPhase and subsequent review phases
            try:
                improve_idx = next(i for i, p in enumerate(self.phases) if isinstance(p, IterativeImprovementPhase))
                active_phases = self.phases[improve_idx:]
            except StopIteration:
                self.logger.warning("IterativeImprovementPhase not found, using all phases.")
        elif project_exists:
            # Handle both factory and direct instance injection
            if callable(self.project_analysis_phase_factory):
                analysis_phase = self.project_analysis_phase_factory()
            else:
                analysis_phase = self.project_analysis_phase_factory

            try:
                logic_phase_index = next(i for i, p in enumerate(self.phases) if isinstance(p, LogicPlanningPhase))
                active_phases = [analysis_phase] + self.phases[logic_phase_index:]
            except StopIteration:
                self.logger.error("LogicPlanningPhase not found, running all phases after analysis.")
                active_phases = [analysis_phase] + self.phases[1:]

        # Initialize Git tool for Issue/PR management if requested
        if kwargs.get("github_integration"):
            self.git_tool = GitPRTool(str(project_root), self.logger)
            if kwargs.get("github_token"):
                import os

                os.environ["GITHUB_TOKEN"] = kwargs.get("github_token")

        loop = self._get_or_create_loop()
        execution_plan = loop.run_until_complete(
            self._setup_and_run_phases_async(
                active_phases,
                project_description,
                project_name,
                project_root,
                project_exists,
                readme_content,
                initial_structure,
                generated_files,
                file_paths,
            )
        )

        self._finalize_project(project_name, project_root, len(file_paths), execution_plan)
        return project_root

    async def _setup_and_run_phases_async(
        self,
        phases: List[IAgentPhase],
        project_description: str,
        project_name: str,
        project_root: Path,
        project_exists: bool,
        readme_content: str,
        initial_structure: dict,
        generated_files: dict,
        file_paths: list,
    ) -> ExecutionPlan:
        """Sets up and runs the execution plan for the given phases with sequential integrity."""
        execution_plan = ExecutionPlan(project_name, is_existing_project=project_exists)
        execution_plan.define_milestones(phases)

        await self.event_publisher.publish(
            "execution_plan_initialized",
            plan=execution_plan.to_dict(),
            milestones=execution_plan.get_milestones_list(),
        )

        # Heartbeat task
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(60)
                    self.logger.heartbeat()
                except asyncio.CancelledError:
                    break

        heartbeat_task = asyncio.create_task(heartbeat_loop())

        # Mejora 6b: Convert to list so we can splice rescue phases in dynamically
        phases = list(phases)

        try:
            for i, phase in enumerate(phases):
                next_phase = phases[i + 1] if i + 1 < len(phases) else None
                keep_alive = "10m" if next_phase else "0s"
                phase_name = phase.__class__.__name__
                milestone_id = execution_plan.get_milestone_id_by_phase_class_name(phase_name)

                self.logger.info(f"🚀 EXECUTING PHASE: {phase_name}")
                if milestone_id:
                    execution_plan.start_milestone(milestone_id)
                    await self.event_publisher.publish("milestone_started", milestone_id=milestone_id, phase=phase_name)

                try:
                    # Run the phase execution
                    (
                        generated_files,
                        initial_structure,
                        file_paths,
                    ) = await phase.execute(
                        project_description=project_description,
                        project_name=project_name,
                        project_root=project_root,
                        readme_content=readme_content,
                        initial_structure=initial_structure,
                        generated_files=generated_files,
                        file_paths=file_paths,
                        context=self.phase_context.ollama_context,
                        options_override={"keep_alive": keep_alive},
                        **self.phase_context.initial_exec_params,
                    )
                    readme_content = generated_files.get("README.md", readme_content)
                    self.phase_context.update_generated_data(
                        generated_files, initial_structure, file_paths, readme_content
                    )

                    # F1: Pick up the enriched description from ClarificationPhase
                    if "__clarified_description__" in generated_files:
                        project_description = generated_files.pop("__clarified_description__")

                    # LogicPlanningPhase specific: Two-pass Issue Creation
                    if isinstance(phase, LogicPlanningPhase) and self.git_tool:
                        self._manage_github_issues(initial_structure)

                    # F40: Store and propagate context
                    if isinstance(generated_files, dict) and "context" in generated_files:
                        ctx = generated_files["context"]
                        self.phase_context.ollama_context = ctx
                        if hasattr(self.llm_manager, "set_global_context"):
                            self.llm_manager.set_global_context(ctx)

                    if milestone_id:
                        summary = f"Phase completed. Files: {len(generated_files)}."
                        execution_plan.complete_milestone(milestone_id, summary)
                        await self.event_publisher.publish(
                            "milestone_completed",
                            milestone_id=milestone_id,
                            phase=phase_name,
                            progress=execution_plan.get_progress(),
                        )

                    # F10: Git checkpoint after each successful phase (feature-flagged)
                    await self._maybe_git_checkpoint(phase_name, project_root)

                    # Cycle of Life: If this was a code generation phase, we might want to PR it
                    if phase_name == "FileContentGenerationPhase":
                        self.logger.info("Cycle of Life: Phase completed, ready for verification.")

                    # Feature 3: Predictive Context Loading — pre-fetch for next phase
                    if next_phase is not None:
                        try:
                            self.phase_context.prefetch_context_for_phase(next_phase.__class__, generated_files)
                        except Exception:
                            pass

                except Exception as e:
                    self.logger.error(f"Error in phase {phase_name}: {e}", exc_info=True)
                    if milestone_id:
                        execution_plan.fail_milestone(milestone_id, str(e))
                        await self.event_publisher.publish(
                            "milestone_failed",
                            milestone_id=milestone_id,
                            phase=phase_name,
                            error=str(e),
                        )
                    await self.event_publisher.publish("phase_error", phase=phase_name, error=str(e))

                    # Mejora 6b: Attempt dynamic rescue planning before aborting
                    rescue_phases = await self._request_rescue_plan(phase_name, str(e))
                    if rescue_phases:
                        self.logger.info(f"[RESCUE] Injecting {len(rescue_phases)} rescue steps after '{phase_name}'")
                        # Splice rescue phases right after current index
                        for offset, rp in enumerate(rescue_phases, start=1):
                            phases.insert(i + offset, rp)
                    else:
                        raise
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        return execution_plan

    async def _request_rescue_plan(self, failed_phase_name: str, error: str) -> List["RescuePhase"]:
        """Ask the LLM for a 3-step rescue plan and return RescuePhase instances (Mejora 6b).

        The rescue plan asks for lightweight context-repair actions that do NOT write
        files — they only log guidance so subsequent phases have richer context.

        Falls back to an empty list if the LLM call fails for any reason (fail-safe).

        Args:
            failed_phase_name: Human-readable phase name that raised an exception.
            error: Error message string (truncated to 500 chars in the prompt).

        Returns:
            List of up to 3 ``RescuePhase`` instances, or empty list on failure.
        """
        system_prompt = (
            "You are a pipeline recovery expert. A phase in an AI code generation pipeline "
            "has failed. Output a JSON array of exactly 3 lightweight recovery steps. "
            "Each step is an object: "
            '{"step": "short title (≤8 words)", "action": "concrete guidance for next phases"}. '
            "Focus on context corrections, not file writes. Output JSON only."
        )
        user_prompt = (
            f"Failed phase: {failed_phase_name}\nError: {error[:500]}\nOutput the JSON array of 3 rescue steps only."
        )
        try:
            response_data, _ = self.llm_manager.get_client("planner").chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[],
            )
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser

            raw = response_data.get("message", {}).get("content", "")
            steps = LLMResponseParser.extract_json(raw)
            if not isinstance(steps, list):
                self.logger.warning("[RESCUE] LLM returned non-list rescue plan; skipping rescue.")
                return []

            rescue_phases: List[RescuePhase] = []
            for idx, step_data in enumerate(steps[:3], start=1):
                if not isinstance(step_data, dict):
                    continue
                rescue_phases.append(
                    RescuePhase(
                        phase_context=self.phase_context,
                        step=str(step_data.get("step", f"Rescue step {idx}")),
                        action=str(step_data.get("action", "")),
                        step_index=idx,
                    )
                )
            return rescue_phases
        except Exception as exc:
            self.logger.warning(f"[RESCUE] Failed to get rescue plan: {exc}")
            return []

    async def _maybe_git_checkpoint(self, phase_name: str, project_root: Any) -> None:
        """Commit all project files as a git checkpoint after a phase succeeds (F10).

        Only runs when ``git_checkpoints.enabled`` is True in agent_features.json
        AND the project_root directory contains a ``.git`` folder (or is any git repo).
        Never raises — checkpoint failures must not abort the pipeline.
        """
        try:
            features = self.config.get("agent_features", {})
            gc_cfg = features.get("git_checkpoints", {})
            if not gc_cfg.get("enabled", False):
                return

            import subprocess  # noqa: PLC0415

            git_dir = project_root / ".git"
            if not git_dir.exists():
                # Auto-init a repo on the first checkpoint so the project has history
                subprocess.run(
                    ["git", "init"],
                    cwd=str(project_root),
                    capture_output=True,
                    check=False,
                    timeout=15,
                )

            prefix = gc_cfg.get("commit_message_prefix", "checkpoint(auto-agent):")
            skip_tag = gc_cfg.get("skip_ci_tag", "[skip ci]")
            msg = f"{prefix} {phase_name} completed {skip_tag}"

            subprocess.run(
                ["git", "add", "--all"],
                cwd=str(project_root),
                capture_output=True,
                check=False,
                timeout=30,
            )
            result = subprocess.run(
                ["git", "commit", "-m", msg, "--allow-empty-message", "--no-gpg-sign"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0:
                # Extract commit hash from "master (root-commit) abc1234] …"
                sha_line = result.stdout.strip().splitlines()[0] if result.stdout else ""
                import re as _re  # noqa: PLC0415

                sha_match = _re.search(r"\b([0-9a-f]{7,40})\b", sha_line)
                sha = sha_match.group(1) if sha_match else "unknown"
                self.phase_context.checkpoint_commits.append(sha)
                self.logger.info(f"[GitCheckpoint] {phase_name} → commit {sha}")
            elif "nothing to commit" in (result.stdout + result.stderr):
                self.logger.debug(f"[GitCheckpoint] {phase_name}: nothing to commit.")
            else:
                self.logger.debug(f"[GitCheckpoint] commit failed for {phase_name}: {result.stderr[:200]}")
        except Exception as exc:
            self.logger.debug(f"[GitCheckpoint] Non-fatal error: {exc}")

    def _manage_github_issues(self, structure: Dict):
        """Implements the 'Dos Pasadas' logic for GitHub issues."""
        self.logger.info("🔗 Starting 'Dos Pasadas' Issue Management...")

        # Prefer backlog from context, fallback to structure tasks
        tasks = (
            self.phase_context.backlog
            if hasattr(self.phase_context, "backlog") and self.phase_context.backlog
            else structure.get("tasks", [])
        )

        if not tasks:
            self.logger.warning("No tasks found in backlog or structure for issue creation.")
            return

        # Pass 1: Create all issues to get IDs
        issue_mapping = {}  # internal_task_id -> github_issue_number
        for task in tasks:
            # Handle different task formats (Dict or internal object)
            task_id = task.get("id") or task.get("task_id")
            title = f"[{task_id}] {task.get('title', 'Untitled Task')}"
            desc = task.get("description", "No description")

            # Professional English "Secretary" Formatting
            body = f"### 📋 Task Description\n{desc}\n\n---\n✨ **Task created by Ollash** 🤖\nInternal ID: `{task_id}`"

            self.logger.info(f"  Pass 1: Creating issue for {task_id}")
            res = self.git_tool.create_issue(title, body)
            if res.get("success"):
                issue_mapping[task_id] = res.get("number")
                task["github_number"] = res.get("number")

        # Guardamos el mapeo para uso externo (PRs en legacy)
        self.phase_context.issue_mapping = issue_mapping

        # Pass 2: Link dependencies
        for task in tasks:
            task_id = task.get("id") or task.get("task_id")
            # The schema specifically uses "dependencies", but we keep depends_on as fallback
            deps = task.get("dependencies") or task.get("depends_on", [])
            github_number = task.get("github_number")

            if deps and github_number:
                self.logger.info(f"  Pass 2: Linking dependencies for issue #{github_number}")
                blocked_by = []
                for dep_id in deps:
                    if dep_id in issue_mapping:
                        blocked_by.append(f"#{issue_mapping[dep_id]}")

                if blocked_by:
                    desc = task.get("description", "")
                    new_body = f"{desc}\n\n🚫 Blocked by: {', '.join(blocked_by)}"
                    self.git_tool.update_issue_body(github_number, new_body)

    async def _update_ollash_manifest(self, current_task_id: str = "N/A") -> str:
        """Generates the content for OLLASH.md manifest."""
        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = await loader.load_prompt("domains/auto_generation/manifest.yaml")

            system = prompts.get("generate_manifest", {}).get("system", "")
            user_template = prompts.get("generate_manifest", {}).get("user", "")

            backlog = getattr(self.phase_context, "backlog", [])
            done = len(
                [t for t in backlog if t.get("github_number") and t.get("status") == "done"]
            )  # Simplified status check
            total = len(backlog) or 1

            backlog_summary = f"{done}/{total} tasks completed."

            current_version = getattr(self.phase_context, "current_version", "v0.1.0")

            # F40: Get vision from context or fallback to description
            initial_params = getattr(self.phase_context, "initial_exec_params", {})
            p_name = initial_params.get("project_name", "Unknown")
            p_desc = initial_params.get("project_description", "N/A")
            p_vision = initial_params.get("project_vision") or p_desc[:500]

            user = user_template.format(
                project_name=p_name,
                project_description=p_desc,
                project_vision=p_vision,
                backlog_summary=backlog_summary,
                current_task=current_task_id,
                current_version=current_version,
                next_tag=f"v0.1.{done + 1}",
                last_decisions="Implemented DevOps standards: Semantic Versioning and Conventional Commits.",
            )

            res, _ = self.llm_manager.get_client("writer").chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}]
            )
            return res.get("content", "").strip()
        except Exception as e:
            self.logger.error(f"Failed to generate manifest: {e}")
            return ""

    def _finalize_project(
        self,
        project_name: str,
        project_root: Path,
        file_count: int,
        execution_plan: ExecutionPlan,
    ):
        """Marks the project as complete and logs final statistics."""
        execution_plan.mark_complete()
        self.event_publisher.publish_sync(
            "execution_plan_completed",
            plan=execution_plan.to_dict(),
            progress=execution_plan.get_progress(),
        )
        self.event_publisher.publish_sync(
            "project_complete",
            project_name=project_name,
            project_root=str(project_root),
            files_generated=file_count,
        )

        self.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.logger.info(f"Knowledge Base Stats: {self.phase_context.error_knowledge_base.get_error_statistics()}")
        # Log fragment cache statistics
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio

                nest_asyncio.apply()
            cache_stats = loop.run_until_complete(self.phase_context.fragment_cache.stats())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            cache_stats = loop.run_until_complete(self.phase_context.fragment_cache.stats())

        self.logger.info(f"Fragment Cache Stats: {cache_stats}")

        plan_file = project_root / "EXECUTION_PLAN.json"
        self.phase_context.file_manager.write_file(plan_file, execution_plan.to_json())

    def generate_structure_only(self, project_description: str, project_name: str, **kwargs) -> Tuple[str, Dict]:
        """Executes only the initial project setup phases."""
        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting structure generation for '{project_name}'.")

        self.phase_context.initial_exec_params = kwargs

        structure_phases = [
            p
            for p in self.phases
            if isinstance(
                p,
                (
                    ReadmeGenerationPhase,
                    StructureGenerationPhase,
                    LogicPlanningPhase,
                    StructurePreReviewPhase,
                ),
            )
        ]

        # F27: Handle existing loops correctly
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(
                self._run_structure_phases_async(structure_phases, project_description, project_name)
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                readme, structure = loop.run_until_complete(
                    self._run_structure_phases_async(structure_phases, project_description, project_name)
                )
                return readme, structure
            finally:
                loop.close()

    async def _run_structure_phases_async(
        self, phases: List[IAgentPhase], project_description: str, project_name: str
    ) -> Tuple[str, Dict]:
        """Helper to run structure-related phases asynchronously."""
        project_root = self.generated_projects_dir / project_name
        generated_files, initial_structure, readme_content, file_paths = {}, {}, "", []

        for i, phase in enumerate(phases):
            next_phase = phases[i + 1] if i + 1 < len(phases) else None
            keep_alive = "10m" if next_phase else "0s"
            self.logger.info(f"Executing phase: {phase.__class__.__name__}")
            generated_files, initial_structure, file_paths = await phase.execute(
                project_description=project_description,
                project_name=project_name,
                project_root=project_root,
                readme_content=readme_content,
                initial_structure=initial_structure,
                generated_files=generated_files,
                file_paths=file_paths,
                context=self.phase_context.ollama_context,
                options_override={"keep_alive": keep_alive},
                **self.phase_context.initial_exec_params,
            )
            readme_content = generated_files.get("README.md", readme_content)
            self.phase_context.update_generated_data(generated_files, initial_structure, file_paths, readme_content)

            # F40: Store and propagate context
            if isinstance(generated_files, dict) and "context" in generated_files:
                ctx = generated_files["context"]
                self.phase_context.ollama_context = ctx
                if hasattr(self.llm_manager, "set_global_context"):
                    self.llm_manager.set_global_context(ctx)

        return readme_content, initial_structure
