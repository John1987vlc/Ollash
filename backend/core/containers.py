"""Dependency Injection containers for the Ollash application."""

from dependency_injector import containers, providers
from pathlib import Path

# Import all services and phases to be managed by the container
from backend.core.config import config
from backend.core.kernel import AgentKernel
from backend.services.llm_client_manager import LLMClientManager

# Core Utilities
from backend.utils.core.structured_logger import StructuredLogger
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.file_manager import FileManager
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.file_validator import FileValidator
from backend.utils.core.documentation_manager import DocumentationManager
from backend.utils.core.event_publisher import EventPublisher
from backend.utils.core.code_quarantine import CodeQuarantine
from backend.utils.core.fragment_cache import FragmentCache
from backend.utils.core.dependency_graph import DependencyGraph
from backend.utils.core.parallel_generator import ParallelFileGenerator
from backend.utils.core.error_knowledge_base import ErrorKnowledgeBase
from backend.utils.core.permission_profiles import PolicyEnforcer, PermissionProfileManager
from backend.utils.core.scanners.rag_context_selector import RAGContextSelector
from backend.utils.core.llm_recorder import LLMRecorder

# Specialized AutoAgent services
from backend.utils.domains.auto_generation.project_planner import ProjectPlanner
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator
from backend.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from backend.utils.domains.auto_generation.file_refiner import FileRefiner
from backend.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from backend.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from backend.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from backend.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from backend.utils.domains.auto_generation.senior_reviewer import SeniorReviewer
from backend.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator
from backend.utils.domains.auto_generation.contingency_planner import ContingencyPlanner
from backend.utils.domains.auto_generation.structure_pre_reviewer import StructurePreReviewer

# Agent Phases
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.project_analysis_phase import ProjectAnalysisPhase
from backend.agents.auto_agent_phases.readme_generation_phase import ReadmeGenerationPhase
from backend.agents.auto_agent_phases.structure_generation_phase import StructureGenerationPhase
from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase
from backend.agents.auto_agent_phases.structure_pre_review_phase import StructurePreReviewPhase
from backend.agents.auto_agent_phases.empty_file_scaffolding_phase import EmptyFileScaffoldingPhase
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from backend.agents.auto_agent_phases.file_refinement_phase import FileRefinementPhase
from backend.agents.auto_agent_phases.verification_phase import VerificationPhase
from backend.agents.auto_agent_phases.code_quarantine_phase import CodeQuarantinePhase
from backend.agents.auto_agent_phases.license_compliance_phase import LicenseCompliancePhase
from backend.agents.auto_agent_phases.dependency_reconciliation_phase import DependencyReconciliationPhase
from backend.agents.auto_agent_phases.test_generation_execution_phase import TestGenerationExecutionPhase
from backend.agents.auto_agent_phases.exhaustive_review_repair_phase import ExhaustiveReviewRepairPhase
from backend.agents.auto_agent_phases.final_review_phase import FinalReviewPhase
from backend.agents.auto_agent_phases.iterative_improvement_phase import IterativeImprovementPhase
from backend.agents.auto_agent_phases.content_completeness_phase import ContentCompletenessPhase
from backend.agents.auto_agent_phases.senior_review_phase import SeniorReviewPhase

from backend.agents.auto_agent import AutoAgent


class CoreContainer(containers.DeclarativeContainer):
    """Container for core, cross-cutting services."""
    config = providers.Object(config)
    ollash_root_dir = providers.Factory(Path, config.provided.get.call("ollash_root_dir", "."))
    generated_projects_dir = providers.Factory(lambda root: root / "generated_projects" / "auto_agent_projects", ollash_root_dir)

    # Create a separate provider for the structured logger
    structured_logger = providers.Singleton(
        StructuredLogger,
        log_file_path=providers.Factory(lambda log_file: Path(log_file), config.provided.get.call("log_file", "ollash.log")),
        logger_name="Ollash",
        log_level=config.provided.get.call("log_level", "debug")
    )
    
    agent_kernel = providers.Singleton(
        AgentKernel, 
        ollash_root_dir=ollash_root_dir.provided,
        structured_logger=structured_logger
    )

    logger = providers.Singleton(AgentLogger, structured_logger=structured_logger, logger_name="OllashApp")
    event_publisher = providers.Singleton(EventPublisher)
    
    tool_settings_config = providers.Singleton(lambda k: k.get_tool_settings_config(), agent_kernel)
    
    command_executor = providers.Singleton(
        CommandExecutor,
        working_dir=ollash_root_dir.provided,
        logger=logger,
        use_docker_sandbox=config.provided.get.call("use_docker_sandbox", False)
    )
    
    file_manager = providers.Singleton(FileManager, root_path=ollash_root_dir.provided)
    response_parser = providers.Singleton(LLMResponseParser)
    file_validator = providers.Singleton(FileValidator, logger=logger, command_executor=command_executor)
    
    llm_recorder = providers.Singleton(LLMRecorder, logger=logger)
    documentation_manager = providers.Singleton(
        DocumentationManager, 
        project_root=ollash_root_dir.provided, 
        logger=logger, 
        llm_recorder=llm_recorder, 
        config=config.provided
    )
    
    code_quarantine = providers.Singleton(CodeQuarantine, project_root=ollash_root_dir.provided, logger=logger)
    
    cache_dir = providers.Factory(lambda root: root / ".cache" / "fragments", ollash_root_dir)
    fragment_cache = providers.Singleton(FragmentCache, cache_dir=cache_dir, logger=logger, enable_persistence=True)
    
    dependency_graph = providers.Singleton(DependencyGraph, logger=logger)
    
    parallel_generator = providers.Singleton(
        ParallelFileGenerator,
        logger=logger,
        max_concurrent=config.provided.get.call("parallel_generation_max_concurrent", 3),
        max_requests_per_minute=config.provided.get.call("parallel_generation_max_rpm", 10)
    )
    
    kb_dir = providers.Factory(lambda root: root / ".cache" / "knowledge", ollash_root_dir)
    error_knowledge_base = providers.Singleton(ErrorKnowledgeBase, knowledge_dir=kb_dir, logger=logger, enable_persistence=True)

    permission_manager = providers.Singleton(
        PermissionProfileManager,
        logger=logger,
        project_root=ollash_root_dir.provided
    )
    policy_enforcer = providers.Singleton(
        PolicyEnforcer,
        profile_manager=permission_manager,
        logger=logger,
        tool_settings_config=tool_settings_config
    )

    rag_context_selector = providers.Singleton(
        RAGContextSelector,
        settings_manager=config.provided,
        project_root=ollash_root_dir.provided,
        logger=logger
    )


class AutoAgentContainer(containers.DeclarativeContainer):
    """Container for AutoAgent and its specific dependencies."""
    core = providers.Container(CoreContainer)
    
    llm_models_config = providers.Singleton(lambda k: k.get_llm_models_config(), core.agent_kernel)

    llm_client_manager = providers.Singleton(
        LLMClientManager, 
        config=llm_models_config,
        tool_settings=core.tool_settings_config,
        logger=core.logger, 
        recorder=core.llm_recorder
    )

    # --- Specialized Service Providers ---
    project_planner = providers.Factory(ProjectPlanner, llm_client=llm_client_manager.provided.get_client.call("planner"), logger=core.logger)
    structure_generator = providers.Factory(StructureGenerator, llm_client=llm_client_manager.provided.get_client.call("prototyper"), logger=core.logger, response_parser=core.response_parser)
    file_content_generator = providers.Factory(FileContentGenerator, llm_client=llm_client_manager.provided.get_client.call("prototyper"), logger=core.logger, response_parser=core.response_parser, documentation_manager=core.documentation_manager, fragment_cache=core.fragment_cache)
    file_refiner = providers.Factory(FileRefiner, llm_client=llm_client_manager.provided.get_client.call("coder"), logger=core.logger, response_parser=core.response_parser, documentation_manager=core.documentation_manager)
    file_completeness_checker = providers.Factory(FileCompletenessChecker, llm_client=llm_client_manager.provided.get_client.call("coder"), logger=core.logger, response_parser=core.response_parser, file_validator=core.file_validator, max_retries_per_file=core.tool_settings_config.provided.completeness_checker_max_retries)
    project_reviewer = providers.Factory(ProjectReviewer, llm_client=llm_client_manager.provided.get_client.call("generalist"), logger=core.logger)
    improvement_suggester = providers.Factory(ImprovementSuggester, llm_client=llm_client_manager.provided.get_client.call("suggester"), logger=core.logger, response_parser=core.response_parser)
    improvement_planner = providers.Factory(ImprovementPlanner, llm_client=llm_client_manager.provided.get_client.call("improvement_planner"), logger=core.logger, response_parser=core.response_parser)
    test_generator = providers.Factory(MultiLanguageTestGenerator, llm_client=llm_client_manager.provided.get_client.call("test_generator"), logger=core.logger, response_parser=core.response_parser, command_executor=core.command_executor)
    senior_reviewer = providers.Factory(SeniorReviewer, llm_client=llm_client_manager.provided.get_client.call("senior_reviewer"), logger=core.logger, response_parser=core.response_parser)
    structure_pre_reviewer = providers.Factory(StructurePreReviewer, llm_client=llm_client_manager.provided.get_client.call("senior_reviewer"), logger=core.logger, response_parser=core.response_parser)
    contingency_planner = providers.Factory(
        ContingencyPlanner, 
        client=llm_client_manager.provided.get_client.call("planner"), 
        logger=core.logger, 
        parser=core.response_parser
    )

    # --- PhaseContext Provider ---
    phase_context = providers.Factory(
        PhaseContext,
        config=core.config,
        logger=core.logger,
        ollash_root_dir=core.ollash_root_dir,
        llm_manager=llm_client_manager,
        response_parser=core.response_parser,
        file_manager=core.file_manager,
        file_validator=core.file_validator,
        documentation_manager=core.documentation_manager,
        event_publisher=core.event_publisher,
        code_quarantine=core.code_quarantine,
        fragment_cache=core.fragment_cache,
        dependency_graph=core.dependency_graph,
        parallel_generator=core.parallel_generator,
        error_knowledge_base=core.error_knowledge_base,
        policy_enforcer=core.policy_enforcer,
        rag_context_selector=core.rag_context_selector,
        project_planner=project_planner,
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
        generated_projects_dir=core.generated_projects_dir
    )
    
    project_analysis_phase_factory = providers.Factory(ProjectAnalysisPhase, context=phase_context)

    # --- Phase Providers ---
    phases_list = providers.List(
        providers.Factory(ReadmeGenerationPhase, context=phase_context),
        providers.Factory(StructureGenerationPhase, context=phase_context),
        providers.Factory(LogicPlanningPhase, context=phase_context),
        providers.Factory(StructurePreReviewPhase, context=phase_context),
        providers.Factory(EmptyFileScaffoldingPhase, context=phase_context),
        providers.Factory(FileContentGenerationPhase, context=phase_context),
        providers.Factory(FileRefinementPhase, context=phase_context),
        providers.Factory(VerificationPhase, context=phase_context),
        providers.Factory(CodeQuarantinePhase, context=phase_context),
        providers.Factory(LicenseCompliancePhase, context=phase_context),
        providers.Factory(DependencyReconciliationPhase, context=phase_context),
        providers.Factory(TestGenerationExecutionPhase, context=phase_context),
        providers.Factory(ExhaustiveReviewRepairPhase, context=phase_context),
        providers.Factory(FinalReviewPhase, context=phase_context),
        providers.Factory(IterativeImprovementPhase, context=phase_context),
        providers.Factory(ContentCompletenessPhase, context=phase_context),
        providers.Factory(SeniorReviewPhase, context=phase_context),
    )
    
    auto_agent = providers.Factory(
        AutoAgent,
        kernel=core.agent_kernel,
        llm_manager=llm_client_manager,
        llm_recorder=core.llm_recorder,
        phase_context=phase_context,
        phases=phases_list,
        project_analysis_phase_factory=project_analysis_phase_factory
    )

class ApplicationContainer(containers.DeclarativeContainer):
    """Top-level container for the entire application."""
    config = providers.Configuration()
    
    core = providers.Container(CoreContainer, config=config)
    auto_agent_module = providers.Container(AutoAgentContainer, core=core)

# Instantiate the main container
main_container = ApplicationContainer(config=config.__dict__)
