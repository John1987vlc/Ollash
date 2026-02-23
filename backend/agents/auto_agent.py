"""
AutoAgent Refactored with Dependency Injection
"""

import asyncio
import datetime
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        **kwargs,
    ):
        super().__init__(
            kernel=kernel,
            logger_name="AutoAgent",
            llm_manager=llm_manager,
            llm_recorder=llm_recorder,
            dependency_scanner=dependency_scanner,
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

    def run(self, project_description: str, project_name: str = "new_project", **kwargs) -> Path:
        """Orchestrates the full project creation pipeline through distinct phases."""
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
                            f"Previous execution of task '{task_id}' failed: "
                            + "; ".join(last_summary.errors)
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

        active_phases = self.phases
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

        self.event_publisher.publish(
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

        try:
            for i, phase in enumerate(phases):
                next_phase = phases[i + 1] if i + 1 < len(phases) else None
                keep_alive = "10m" if next_phase else "0s"
                phase_name = phase.__class__.__name__
                milestone_id = execution_plan.get_milestone_id_by_phase_class_name(phase_name)

                self.logger.info(f"🚀 EXECUTING PHASE: {phase_name}")
                if milestone_id:
                    execution_plan.start_milestone(milestone_id)
                    self.event_publisher.publish("milestone_started", milestone_id=milestone_id, phase=phase_name)

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
                        self.event_publisher.publish(
                            "milestone_completed",
                            milestone_id=milestone_id,
                            phase=phase_name,
                            progress=execution_plan.get_progress(),
                        )

                    # Cycle of Life: If this was a code generation phase, we might want to PR it
                    if phase_name == "FileContentGenerationPhase":
                        self.logger.info("Cycle of Life: Phase completed, ready for verification.")

                except Exception as e:
                    self.logger.error(f"Error in phase {phase_name}: {e}", exc_info=True)
                    if milestone_id:
                        execution_plan.fail_milestone(milestone_id, str(e))
                        self.event_publisher.publish(
                            "milestone_failed",
                            milestone_id=milestone_id,
                            phase=phase_name,
                            error=str(e),
                        )
                    self.event_publisher.publish("phase_error", phase=phase_name, error=str(e))
                    raise
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        return execution_plan

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
            prompts = loader.load_prompt("domains/auto_generation/manifest.yaml")

            system = prompts.get("generate_manifest", {}).get("system", "")
            user_template = prompts.get("generate_manifest", {}).get("user", "")

            backlog = getattr(self.phase_context, "backlog", [])
            done = len(
                [t for t in backlog if t.get("github_number") and t.get("status") == "done"]
            )  # Simplified status check
            total = len(backlog) or 1

            backlog_summary = f"{done}/{total} tasks completed."

            current_version = getattr(self.phase_context, "current_version", "v0.1.0")

            user = user_template.format(
                project_name=self.phase_context.initial_exec_params.get("project_name", "Unknown"),
                project_description=self.phase_context.initial_exec_params.get("project_description", "N/A"),
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
        self.event_publisher.publish(
            "execution_plan_completed",
            plan=execution_plan.to_dict(),
            progress=execution_plan.get_progress(),
        )
        self.event_publisher.publish(
            "project_complete",
            project_name=project_name,
            project_root=str(project_root),
            files_generated=file_count,
        )

        self.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.logger.info(f"Knowledge Base Stats: {self.phase_context.error_knowledge_base.get_error_statistics()}")
        self.logger.info(f"Fragment Cache Stats: {self.phase_context.fragment_cache.stats()}")

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
