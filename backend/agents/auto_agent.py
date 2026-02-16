"""
AutoAgent Refactored with Dependency Injection
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dependency_injector import providers
from dependency_injector.wiring import Provide, inject

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
from backend.utils.core.execution_plan import ExecutionPlan

# Core utilities
from backend.utils.core.llm_recorder import LLMRecorder


class AutoAgent(CoreAgent):
    """
    Orchestrates the multi-phase project creation pipeline using injected dependencies.
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
        **kwargs,
    ):
        super().__init__(
            kernel=kernel,
            logger_name="AutoAgent",
            llm_manager=llm_manager,
            llm_recorder=llm_recorder,
        )

        self.config = self.kernel.get_full_config()
        self.logger.info("AutoAgent initializing with injected dependencies.")

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

        self.logger.info("AutoAgent initialized with a modular phase pipeline.")

    def run(self, project_description: str, project_name: str = "new_project", **kwargs) -> Path:
        """Orchestrates the full project creation pipeline through distinct phases."""
        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting full generation for '{project_name}'.")

        project_root = self.generated_projects_dir / project_name
        project_exists = project_root.exists() and any(project_root.iterdir())

        if project_exists:
            self.logger.info(f"📁 Existing project detected at {project_root}")
            (
                generated_files,
                initial_structure,
                file_paths,
            ) = self.phase_context.ingest_existing_project(project_root)
            readme_content = generated_files.get("README.md", "")
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
        if project_exists:
            analysis_phase = self.project_analysis_phase_factory()
            try:
                logic_phase_index = next(i for i, p in enumerate(self.phases) if isinstance(p, LogicPlanningPhase))
                active_phases = [analysis_phase] + self.phases[logic_phase_index:]
            except StopIteration:
                self.logger.error("LogicPlanningPhase not found, running all phases after analysis.")
                active_phases = [analysis_phase] + self.phases[1:]

        execution_plan = self._setup_and_run_phases(
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

        self._finalize_project(project_name, project_root, len(file_paths), execution_plan)
        return project_root

    def _setup_and_run_phases(
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
        """Sets up and runs the execution plan for the given phases."""
        execution_plan = ExecutionPlan(project_name, is_existing_project=project_exists)
        execution_plan.define_milestones(phases)

        self.event_publisher.publish(
            "execution_plan_initialized",
            plan=execution_plan.to_dict(),
            milestones=execution_plan.get_milestones_list(),
        )

        for phase in phases:
            phase_name = phase.__class__.__name__
            milestone_id = execution_plan.get_milestone_id_by_phase_class_name(phase_name)

            self.logger.info(f"Executing phase: {phase_name}")
            if milestone_id:
                execution_plan.start_milestone(milestone_id)
                self.event_publisher.publish("milestone_started", milestone_id=milestone_id, phase=phase_name)

            try:
                # Run the phase execution asynchronously
                loop = asyncio.get_event_loop()
                (
                    generated_files,
                    initial_structure,
                    file_paths,
                ) = loop.run_until_complete(
                    phase.execute(
                        project_description=project_description,
                        project_name=project_name,
                        project_root=project_root,
                        readme_content=readme_content,
                        initial_structure=initial_structure,
                        generated_files=generated_files,
                        file_paths=file_paths,
                        **self.phase_context.initial_exec_params,
                    )
                )
                readme_content = generated_files.get("README.md", readme_content)
                self.phase_context.update_generated_data(generated_files, initial_structure, file_paths, readme_content)

                if milestone_id:
                    summary = f"Phase completed. Files: {len(generated_files)}."
                    execution_plan.complete_milestone(milestone_id, summary)
                    self.event_publisher.publish(
                        "milestone_completed",
                        milestone_id=milestone_id,
                        phase=phase_name,
                        progress=execution_plan.get_progress(),
                    )

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

        return execution_plan

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

        # This method is often called from a sync context, so it needs to manage its own event loop
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

        for phase in phases:
            self.logger.info(f"Executing phase: {phase.__class__.__name__}")
            generated_files, initial_structure, file_paths = await phase.execute(
                project_description=project_description,
                project_name=project_name,
                project_root=project_root,
                readme_content=readme_content,
                initial_structure=initial_structure,
                generated_files=generated_files,
                file_paths=file_paths,
                **self.phase_context.initial_exec_params,
            )
            readme_content = generated_files.get("README.md", readme_content)
            self.phase_context.update_generated_data(generated_files, initial_structure, file_paths, readme_content)

        return readme_content, initial_structure
