import json
import os
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# Core Agent and Kernel
from src.agents.core_agent import CoreAgent
from src.core.kernel import AgentKernel # Import AgentKernel
from src.interfaces.imodel_provider import IModelProvider # For type hinting

# NEW Imports for AutoAgent Phases and Context
from src.interfaces.iagent_phase import IAgentPhase
from src.agents.auto_agent_phases.phase_context import PhaseContext
from src.agents.auto_agent_phases.readme_generation_phase import ReadmeGenerationPhase
from src.agents.auto_agent_phases.structure_generation_phase import StructureGenerationPhase
from src.agents.auto_agent_phases.structure_pre_review_phase import StructurePreReviewPhase
from src.agents.auto_agent_phases.empty_file_scaffolding_phase import EmptyFileScaffoldingPhase
from src.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from src.agents.auto_agent_phases.file_refinement_phase import FileRefinementPhase
from src.agents.auto_agent_phases.verification_phase import VerificationPhase
from src.agents.auto_agent_phases.code_quarantine_phase import CodeQuarantinePhase
from src.agents.auto_agent_phases.license_compliance_phase import LicenseCompliancePhase
from src.agents.auto_agent_phases.dependency_reconciliation_phase import DependencyReconciliationPhase
from src.agents.auto_agent_phases.test_generation_execution_phase import TestGenerationExecutionPhase
from src.agents.auto_agent_phases.final_review_phase import FinalReviewPhase
from src.agents.auto_agent_phases.iterative_improvement_phase import IterativeImprovementPhase
from src.agents.auto_agent_phases.content_completeness_phase import ContentCompletenessPhase
from src.agents.auto_agent_phases.senior_review_phase import SeniorReviewPhase


# Existing Utility Imports (now mostly passed via PhaseContext)
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.file_manager import FileManager
from src.utils.core.file_validator import FileValidator
from src.utils.core.documentation_manager import DocumentationManager
from src.utils.core.event_publisher import EventPublisher
from src.utils.core.code_quarantine import CodeQuarantine
from src.utils.core.fragment_cache import FragmentCache
from src.utils.core.dependency_graph import DependencyGraph
from src.utils.core.parallel_generator import ParallelFileGenerator
from src.utils.core.error_knowledge_base import ErrorKnowledgeBase
from src.utils.core.permission_profiles import PolicyEnforcer
from src.utils.core.scanners.rag_context_selector import RAGContextSelector
from src.utils.core.command_executor import CommandExecutor # For test_generator and policy_enforcer init
from src.utils.core.llm_recorder import LLMRecorder # NEW: Import LLMRecorder

# Specialized AutoAgent services
from src.utils.domains.auto_generation.project_planner import ProjectPlanner
from src.utils.domains.auto_generation.structure_generator import StructureGenerator
from src.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from src.utils.domains.auto_generation.file_refiner import FileRefiner
from src.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from src.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from src.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from src.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from src.utils.domains.auto_generation.senior_reviewer import SeniorReviewer
from src.utils.domains.auto_generation.test_generator import TestGenerator as LegacyTestGenerator # Renamed to avoid conflict
from src.utils.domains.auto_generation.contingency_planner import ContingencyPlanner
from src.utils.domains.auto_generation.structure_pre_reviewer import StructurePreReviewer
from src.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator


class AutoAgent(CoreAgent):
    """
    Orchestrates the multi-phase project creation pipeline, delegating
    each phase to specialized IAgentPhase implementations.
    """

    def __init__(self,
                 config_path: str = "config/settings.json", # Kept for backward compatibility for now
                 ollash_root_dir: Optional[Path] = None,
                 kernel: Optional[AgentKernel] = None,
                 llm_manager: Optional[IModelProvider] = None,
                 llm_recorder: Optional[LLMRecorder] = None): # NEW: Add llm_recorder
        # Initialize AgentKernel if not provided
        if kernel:
            self.kernel = kernel
        else:
            # Ensure ollash_root_dir is resolved for AgentKernel init if not provided
            resolved_ollash_root_dir = ollash_root_dir if ollash_root_dir else Path(os.getcwd())
            self.kernel = AgentKernel(config_dir=Path(config_path).parent, ollash_root_dir=resolved_ollash_root_dir)
        
        # Call parent constructor, passing the kernel, llm_manager, and llm_recorder
        super().__init__(kernel=self.kernel, logger_name="AutoAgent", llm_manager=llm_manager, llm_recorder=llm_recorder)
        
        # Ensure config and logger are accessible (they are set by CoreAgent's __init__)
        self.config = self.kernel.get_full_config()
        self.logger = self.kernel.get_logger()

        self.logger.info("AutoAgent specific initialization.")

        # Ensure llm_manager is available (either injected or from super().__init__)
        if not self.llm_manager:
            raise ValueError("LLMClientManager (or IModelProvider) must be provided to AutoAgent.")
        
        # --- Initialize Core Services that will go into PhaseContext ---
        response_parser = LLMResponseParser()
        file_manager = FileManager(str(self.ollash_root_dir))
        command_executor = CommandExecutor(
            working_dir=str(self.ollash_root_dir),
            logger=self.logger,
            use_docker_sandbox=self.config.get("use_docker_sandbox", False)
        )
        file_validator = FileValidator(logger=self.logger, command_executor=command_executor)
        documentation_manager = self.documentation_manager # From CoreAgent
        event_publisher = self.event_publisher # From CoreAgent
        code_quarantine = CodeQuarantine(self.ollash_root_dir, self.logger)
        
        cache_dir = self.ollash_root_dir / ".cache" / "fragments"
        fragment_cache = FragmentCache(cache_dir, self.logger, enable_persistence=True)
        fragment_cache.preload_common_fragments("python")
        fragment_cache.preload_common_fragments("javascript")
        
        dependency_graph = DependencyGraph(self.logger)
        parallel_generator = ParallelFileGenerator(
            self.logger, max_concurrent=self.config.get("parallel_generation_max_concurrent", 3),
            max_requests_per_minute=self.config.get("parallel_generation_max_rpm", 10)
        )
        kb_dir = self.ollash_root_dir / ".cache" / "knowledge"
        error_knowledge_base = ErrorKnowledgeBase(kb_dir, self.logger, enable_persistence=True)
        
        policy_enforcer = self.policy_enforcer # From CoreAgent
        rag_context_selector = self.rag_context_selector # From CoreAgent

        # --- Initialize Specialized AutoAgent Services ---
        planner = ProjectPlanner(self.llm_manager.get_client("planner"), self.logger)
        structure_generator = StructureGenerator(
            self.llm_manager.get_client("prototyper"), self.logger, response_parser
        )
        file_content_generator = FileContentGenerator(
            self.llm_manager.get_client("prototyper"), self.logger, response_parser, 
            documentation_manager, fragment_cache
        )
        file_refiner = FileRefiner(
            self.llm_manager.get_client("coder"), self.logger, response_parser, documentation_manager, event_publisher
        )
        file_completeness_checker = FileCompletenessChecker(
            self.llm_manager.get_client("coder"),
            self.logger,
            response_parser,
            file_validator,
            max_retries_per_file=self.config.get("completeness_checker_max_retries", 2),
        )
        project_reviewer = ProjectReviewer(self.llm_manager.get_client("generalist"), self.logger)
        improvement_suggester = ImprovementSuggester(
            self.llm_manager.get_client("suggester"), self.logger, response_parser
        )
        improvement_planner = ImprovementPlanner(
            self.llm_manager.get_client("improvement_planner"), self.logger, response_parser
        )
        test_generator = MultiLanguageTestGenerator(
            self.llm_manager.get_client("test_generator"), self.logger, response_parser, command_executor
        )
        senior_reviewer = SeniorReviewer(
            self.llm_manager.get_client("senior_reviewer"), self.logger, response_parser
        )
        structure_pre_reviewer = StructurePreReviewer(
            self.llm_manager.get_client("senior_reviewer"), self.logger, response_parser
        )
        contingency_planner = ContingencyPlanner(
            self.llm_manager.get_client("planner"), self.logger, response_parser
        )
        self.generated_projects_dir = self.ollash_root_dir / "generated_projects" / "auto_agent_projects"
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)


        # --- Initialize PhaseContext ---
        self.phase_context = PhaseContext(
            config=self.config,
            logger=self.logger,
            ollash_root_dir=self.ollash_root_dir,
            llm_manager=self.llm_manager,
            response_parser=response_parser,
            file_manager=file_manager,
            file_validator=file_validator,
            documentation_manager=documentation_manager,
            event_publisher=event_publisher,
            code_quarantine=code_quarantine,
            fragment_cache=fragment_cache,
            dependency_graph=dependency_graph,
            parallel_generator=parallel_generator,
            error_knowledge_base=error_knowledge_base,
            policy_enforcer=policy_enforcer,
            rag_context_selector=rag_context_selector,
            project_planner=planner,
            structure_generator=structure_generator,
            file_content_generator=file_content_generator,
            file_refiner=file_refiner,
            file_completeness_checker=file_completeness_checker,
            project_reviewer=project_reviewer,
            improvement_suggester=improvement_suggester,
            improvement_planner=improvement_planner,
            senior_reviewer=senior_reviewer,
            test_generator=test_generator,
            contingency_planner=contingency_planner,
            structure_pre_reviewer=structure_pre_reviewer,
            generated_projects_dir=self.generated_projects_dir,
            auto_agent=self # Pass self for now, to enable _reconcile_requirements access
        )

        # --- Define the ordered pipeline of phases ---
        self.phases: List[IAgentPhase] = [
            ReadmeGenerationPhase(self.phase_context),
            StructureGenerationPhase(self.phase_context),
            StructurePreReviewPhase(self.phase_context),
            EmptyFileScaffoldingPhase(self.phase_context),
            FileContentGenerationPhase(self.phase_context),
            FileRefinementPhase(self.phase_context),
            VerificationPhase(self.phase_context),
            CodeQuarantinePhase(self.phase_context),
            LicenseCompliancePhase(self.phase_context),
            DependencyReconciliationPhase(self.phase_context),
            TestGenerationExecutionPhase(self.phase_context),
            FinalReviewPhase(self.phase_context),
            IterativeImprovementPhase(self.phase_context),
            ContentCompletenessPhase(self.phase_context),
            SeniorReviewPhase(self.phase_context),
        ]
        self.logger.info("AutoAgent initialized with a modular phase pipeline.")

    def run(self, project_description: str, project_name: str = "new_project", num_refine_loops: int = 0,
            template_name: str = "default", python_version: str = "3.12", license_type: str = "MIT",
            include_docker: bool = False) -> Path:
        """Orchestrates the full project creation pipeline through distinct phases."""
        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting full generation for '{project_name}'.")

        project_root = self.generated_projects_dir / project_name
        project_root.mkdir(parents=True, exist_ok=True)

        generated_files: Dict[str, str] = {}
        initial_structure: Dict[str, Any] = {}
        readme_content: str = ""
        file_paths: List[str] = []

        # Store initial execution parameters in context for phases that might need them
        self.phase_context.initial_exec_params = {
            "template_name": template_name,
            "python_version": python_version,
            "license_type": license_type,
            "include_docker": include_docker,
            "num_refine_loops": num_refine_loops,
        }

        for phase in self.phases:
            self.logger.info(f"Executing phase: {phase.__class__.__name__}")
            try:
                # Execute the phase, passing the current state and parameters
                generated_files, initial_structure, file_paths = asyncio.run(phase.execute(
                    project_description=project_description,
                    project_name=project_name,
                    project_root=project_root,
                    readme_content=readme_content,
                    initial_structure=initial_structure,
                    generated_files=generated_files,
                    file_paths=file_paths, # Pass file_paths explicitly
                    **self.phase_context.initial_exec_params # Pass initial params to all phases
                ))
                # Update readme_content if it was generated in a phase
                readme_content = generated_files.get("README.md", readme_content)

                # Update context with current state after each phase
                self.phase_context.update_generated_data(
                    generated_files, initial_structure, file_paths, readme_content
                )
            except Exception as e:
                self.logger.error(f"Error executing phase {phase.__class__.__name__}: {e}")
                self.event_publisher.publish("phase_error", phase=phase.__class__.__name__, error=str(e))
                # Depending on the error, we might want to break, retry, or contingency plan
                raise

        self.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.event_publisher.publish("project_complete", project_name=project_name, project_root=str(project_root), files_generated=len(file_paths))
        
        # Log knowledge base statistics
        kb_stats = self.phase_context.error_knowledge_base.get_error_statistics()
        self.logger.info(f"Knowledge Base Stats: {kb_stats}")
        
        # Log fragment cache statistics  
        cache_stats = self.phase_context.fragment_cache.stats()
        self.logger.info(f"Fragment Cache Stats: {cache_stats}")
        
        return project_root
    
    # The generate_structure_only and continue_generation methods are no longer needed
    # as the entire pipeline is orchestrated by the run method using phases.
    # We keep them here for now, but they will be removed once clients are updated.
    def generate_structure_only(self, project_description: str, project_name: str, template_name: str = "default",
                                python_version: str = "3.12", license_type: str = "MIT",
                                include_docker: bool = False) -> Tuple[str, Dict]:
        raise NotImplementedError("generate_structure_only is deprecated. Use run() directly with appropriate parameters.")
    
    def continue_generation(self, project_description: str, project_name: str, readme: str, structure: Dict,
                            template_name: str = "default", python_version: str = "3.12", license_type: str = "MIT",
                            include_docker: bool = False, num_refine_loops: int = 0) -> Path:
        raise NotImplementedError("continue_generation is deprecated. Use run() directly with appropriate parameters.")

    # These helper methods are now part of PhaseContext
    # def _infer_language(self, file_path: str) -> str: pass
    # def _group_files_by_language(self, files: Dict[str, str]) -> Dict[str, List[Tuple[str, str]]]: pass
    # def _get_test_file_path(self, source_file: str, language: str) -> str: pass
    # def _implement_plan(self, plan: Dict, project_root: Path, readme: str, structure: Dict, files: Dict[str, str], file_paths: List[str]) -> Tuple[Dict[str, str], Dict, List[str]]: pass
    # def _select_related_files(self, target_path: str, generated_files: Dict[str, str], max_files: int = 8) -> Dict[str, str]: pass

