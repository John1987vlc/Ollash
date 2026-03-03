"""Dependency Injection containers for the Ollash application."""

from pathlib import Path

from dependency_injector import containers, providers

from backend.agents.auto_agent import AutoAgent
from backend.agents.auto_agent_phases.cicd_healing_phase import CICDHealingPhase
from backend.agents.auto_agent_phases.code_quarantine_phase import CodeQuarantinePhase
from backend.agents.auto_agent_phases.content_completeness_phase import ContentCompletenessPhase
from backend.agents.auto_agent_phases.dependency_reconciliation_phase import DependencyReconciliationPhase
from backend.agents.auto_agent_phases.documentation_deploy_phase import DocumentationDeployPhase
from backend.agents.auto_agent_phases.empty_file_scaffolding_phase import EmptyFileScaffoldingPhase
from backend.agents.auto_agent_phases.exhaustive_review_repair_phase import ExhaustiveReviewRepairPhase
from backend.agents.auto_agent_phases.chaos_injection_phase import ChaosInjectionPhase
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from backend.agents.auto_agent_phases.file_refinement_phase import FileRefinementPhase
from backend.agents.auto_agent_phases.final_review_phase import FinalReviewPhase
from backend.agents.auto_agent_phases.infrastructure_generation_phase import InfrastructureGenerationPhase
from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase
from backend.agents.auto_agent_phases.iterative_improvement_phase import IterativeImprovementPhase
from backend.agents.auto_agent_phases.javascript_optimization_phase import JavaScriptOptimizationPhase
from backend.agents.auto_agent_phases.license_compliance_phase import LicenseCompliancePhase
from backend.agents.auto_agent_phases.interface_scaffolding_phase import InterfaceScaffoldingPhase
from backend.agents.auto_agent_phases.logic_planning_phase import LogicPlanningPhase

# Agent Phases
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.project_analysis_phase import ProjectAnalysisPhase
from backend.agents.auto_agent_phases.readme_generation_phase import ReadmeGenerationPhase
from backend.agents.auto_agent_phases.security_scan_phase import SecurityScanPhase
from backend.agents.auto_agent_phases.senior_review_phase import SeniorReviewPhase
from backend.agents.auto_agent_phases.structure_generation_phase import StructureGenerationPhase
from backend.agents.auto_agent_phases.structure_pre_review_phase import StructurePreReviewPhase
from backend.agents.auto_agent_phases.generation_execution_phase import TestGenerationExecutionPhase
from backend.agents.auto_agent_phases.verification_phase import VerificationPhase
from backend.agents.auto_agent_phases.web_smoke_test_phase import WebSmokeTestPhase

# Sprint 10 — 10 new pipeline phases
from backend.agents.auto_agent_phases.clarification_phase import ClarificationPhase
from backend.agents.auto_agent_phases.viability_estimator_phase import ViabilityEstimatorPhase
from backend.agents.auto_agent_phases.test_planning_phase import TestPlanningPhase
from backend.agents.auto_agent_phases.component_tree_phase import ComponentTreePhase
from backend.agents.auto_agent_phases.api_contract_phase import ApiContractPhase
from backend.agents.auto_agent_phases.plan_validation_phase import PlanValidationPhase
from backend.agents.auto_agent_phases.dependency_precheck_phase import DependencyPrecheckPhase

from backend.core.config import config
from backend.core.kernel import AgentKernel
from backend.services.llm_client_manager import LLMClientManager
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.cicd_healer import CICDHealer
from backend.utils.core.analysis.code_quarantine import CodeQuarantine
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.analysis.dependency_graph import DependencyGraph
from backend.utils.core.io.documentation_manager import DocumentationManager
from backend.utils.core.memory.error_knowledge_base import ErrorKnowledgeBase
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.io.export_manager import ExportManager
from backend.utils.core.io.locked_file_manager import LockedFileManager
from backend.utils.core.analysis.file_validator import FileValidator
from backend.utils.core.memory.fragment_cache import FragmentCache
from backend.utils.core.memory.episodic_memory import EpisodicMemory
from backend.utils.core.analysis.shadow_evaluator import ShadowEvaluator
from backend.utils.core.llm.llm_recorder import LLMRecorder
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.parallel_generator import ParallelFileGenerator
from backend.utils.core.llm.prompt_repository import PromptRepository
from backend.utils.core.llm.prompt_loader import PromptLoader
from backend.utils.core.system.permission_profiles import PermissionProfileManager, PolicyEnforcer
from backend.utils.core.analysis.scanners.rag_context_selector import RAGContextSelector
from backend.utils.core.analysis.scanners.dependency_scanner import DependencyScanner
from backend.utils.core.analysis.vulnerability_scanner import VulnerabilityScanner
from backend.utils.core.system.structured_logger import StructuredLogger
from backend.utils.domains.auto_generation.contingency_planner import ContingencyPlanner
from backend.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from backend.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from backend.utils.domains.auto_generation.file_refiner import FileRefiner
from backend.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from backend.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from backend.utils.domains.auto_generation.infra_generator import InfraGenerator
from backend.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator
from backend.utils.domains.auto_generation.project_planner import ProjectPlanner
from backend.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from backend.utils.domains.auto_generation.senior_reviewer import SeniorReviewer
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator
from backend.utils.domains.auto_generation.code_patcher import CodePatcher
from backend.utils.domains.auto_generation.structure_pre_reviewer import StructurePreReviewer

# Domain Agent imports (Agent-per-Domain architecture)
from backend.agents.domain_agents.architect_agent import ArchitectAgent
from backend.agents.domain_agents.auditor_agent import AuditorAgent
from backend.agents.domain_agents.developer_agent import DeveloperAgent
from backend.agents.domain_agents.devops_agent import DevOpsAgent
from backend.agents.domain_agent_orchestrator import DomainAgentOrchestrator
from backend.agents.orchestrators.blackboard import Blackboard
from backend.agents.orchestrators.self_healing_loop import SelfHealingLoop
from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher
from backend.agents.orchestrators.debate_node_runner import DebateNodeRunner
from backend.utils.domains.code.sandbox_runner import SandboxRunner
from backend.utils.core.io.checkpoint_manager import CheckpointManager
from backend.utils.core.analysis.cost_analyzer import CostAnalyzer
from backend.utils.core.system.metrics_database import MetricsDatabase


# ---------------------------------------------------------------------------
# Sub-containers (semantic grouping)
# ---------------------------------------------------------------------------


class LoggingContainer(containers.DeclarativeContainer):
    """Logging, kernel, and event infrastructure."""

    config = providers.Dependency()
    ollash_root_dir = providers.Dependency()

    structured_logger = providers.Singleton(
        StructuredLogger,
        log_file_path=providers.Factory(
            lambda log_file: Path(log_file),
            config.provided.get.call("log_file", "ollash.log"),
        ),
        logger_name="Ollash",
        log_level=config.provided.get.call("log_level", "debug"),
    )

    agent_kernel = providers.Singleton(
        AgentKernel,
        ollash_root_dir=ollash_root_dir,
        structured_logger=structured_logger,
    )

    logger = providers.Singleton(AgentLogger, structured_logger=structured_logger, logger_name="OllashApp")
    event_publisher = providers.Singleton(EventPublisher)
    tool_settings_config = providers.Singleton(lambda k: k.get_tool_settings_config(), agent_kernel)


class StorageContainer(containers.DeclarativeContainer):
    """File system, caching, and parsing services."""

    logger = providers.Dependency()
    ollash_root_dir = providers.Dependency()
    command_executor = providers.Dependency()

    file_manager = providers.Singleton(LockedFileManager, root_path=ollash_root_dir, logger=logger)
    response_parser = providers.Singleton(LLMResponseParser)
    file_validator = providers.Singleton(FileValidator, logger=logger, command_executor=command_executor)

    cache_dir = providers.Factory(lambda root: root / ".cache" / "fragments", ollash_root_dir)
    fragment_cache = providers.Singleton(FragmentCache, cache_dir=cache_dir, logger=logger, enable_persistence=True)


class AnalysisContainer(containers.DeclarativeContainer):
    """Code analysis, RAG, and evaluation services."""

    logger = providers.Dependency()
    ollash_root_dir = providers.Dependency()
    event_publisher = providers.Dependency()
    config = providers.Dependency()

    code_quarantine = providers.Singleton(CodeQuarantine, project_root=ollash_root_dir, logger=logger)
    dependency_graph = providers.Singleton(DependencyGraph, logger=logger)
    dependency_scanner = providers.Singleton(DependencyScanner, logger=logger)

    shadow_evaluator = providers.Singleton(
        ShadowEvaluator,
        logger=logger,
        event_publisher=event_publisher,
        log_dir=providers.Factory(lambda root: root / "logs" / "shadow", ollash_root_dir),
    )

    rag_context_selector = providers.Singleton(
        RAGContextSelector,
        settings_manager=config,
        project_root=ollash_root_dir,
        logger=logger,
    )

    vulnerability_scanner = providers.Singleton(VulnerabilityScanner, logger=logger)


class SecurityContainer(containers.DeclarativeContainer):
    """Permission profiles and policy enforcement."""

    logger = providers.Dependency()
    ollash_root_dir = providers.Dependency()
    tool_settings_config = providers.Dependency()

    permission_manager = providers.Singleton(PermissionProfileManager, logger=logger, project_root=ollash_root_dir)
    policy_enforcer = providers.Singleton(
        PolicyEnforcer,
        profile_manager=permission_manager,
        logger=logger,
        tool_settings_config=tool_settings_config,
    )


class MemoryContainer(containers.DeclarativeContainer):
    """Long-term memory and knowledge base services."""

    logger = providers.Dependency()
    ollash_root_dir = providers.Dependency()

    kb_dir = providers.Factory(lambda root: root / ".cache" / "knowledge", ollash_root_dir)
    error_knowledge_base = providers.Singleton(
        ErrorKnowledgeBase, knowledge_dir=kb_dir, logger=logger, enable_persistence=True
    )
    episodic_memory = providers.Singleton(EpisodicMemory, memory_dir=ollash_root_dir, logger=logger)


# ---------------------------------------------------------------------------
# Core container — composes sub-containers and holds shared cross-cutting deps
# ---------------------------------------------------------------------------


class CoreContainer(containers.DeclarativeContainer):
    """Core application services. Composes semantic sub-containers.

    Sub-container access paths:
      core.logging.logger         — AgentLogger
      core.logging.agent_kernel   — AgentKernel
      core.logging.event_publisher — EventPublisher
      core.logging.tool_settings_config — ToolSettingsConfig
      core.storage.file_manager   — FileManager
      core.storage.response_parser — LLMResponseParser
      core.storage.file_validator  — FileValidator
      core.storage.fragment_cache  — FragmentCache
      core.analysis.code_quarantine / dependency_graph / dependency_scanner
      core.analysis.shadow_evaluator / rag_context_selector / vulnerability_scanner
      core.security.permission_manager / policy_enforcer
      core.memory.error_knowledge_base / episodic_memory
    """

    config = providers.Object(config)
    ollash_root_dir = providers.Factory(Path, config.provided.get.call("ollash_root_dir", "."))
    generated_projects_dir = providers.Factory(
        lambda root: root / "generated_projects" / "auto_agent_projects",
        ollash_root_dir,
    )

    # Logging sub-container defined first — others depend on logging.logger
    logging = providers.Container(
        LoggingContainer,
        config=config,
        ollash_root_dir=ollash_root_dir,
    )

    command_executor = providers.Singleton(
        CommandExecutor,
        working_dir=ollash_root_dir.provided,
        logger=logging.logger,
        use_docker_sandbox=config.provided.get.call("use_docker_sandbox", False),
    )

    storage = providers.Container(
        StorageContainer,
        logger=logging.logger,
        ollash_root_dir=ollash_root_dir,
        command_executor=command_executor,
    )
    analysis = providers.Container(
        AnalysisContainer,
        logger=logging.logger,
        ollash_root_dir=ollash_root_dir,
        event_publisher=logging.event_publisher,
        config=config.provided,
    )
    security = providers.Container(
        SecurityContainer,
        logger=logging.logger,
        ollash_root_dir=ollash_root_dir,
        tool_settings_config=logging.tool_settings_config,
    )
    memory = providers.Container(
        MemoryContainer,
        logger=logging.logger,
        ollash_root_dir=ollash_root_dir,
    )

    # Shared cross-cutting providers (used by AutoAgent and multiple sub-systems)
    llm_recorder = providers.Singleton(LLMRecorder, logger=logging.logger)
    token_tracker = providers.Singleton(TokenTracker)

    prompt_loader = providers.Singleton(
        PromptLoader,
        prompts_dir=providers.Factory(lambda root: root / "prompts", ollash_root_dir),
    )
    prompt_db_path = providers.Factory(lambda root: root / ".ollash" / "prompt_history.db", ollash_root_dir)
    prompt_repository = providers.Singleton(PromptRepository, db_path=prompt_db_path)

    documentation_manager = providers.Singleton(
        DocumentationManager,
        project_root=ollash_root_dir.provided,
        logger=logging.logger,
        llm_recorder=llm_recorder,
        config=config.provided,
    )

    parallel_generator = providers.Singleton(
        ParallelFileGenerator,
        logger=logging.logger,
        max_concurrent=config.provided.get.call("parallel_generation_max_concurrent", 3),
        max_requests_per_minute=config.provided.get.call("parallel_generation_max_rpm", 10),
    )

    export_manager = providers.Singleton(
        ExportManager,
        command_executor=command_executor,
        logger=logging.logger,
    )


# ---------------------------------------------------------------------------
# AutoAgent container
# ---------------------------------------------------------------------------


class AutoAgentContainer(containers.DeclarativeContainer):
    """Container for AutoAgent and its specific dependencies."""

    core = providers.Container(CoreContainer)

    llm_models_config = providers.Singleton(lambda k: k.get_llm_models_config(), core.logging.agent_kernel)

    llm_client_manager = providers.Singleton(
        LLMClientManager,
        config=llm_models_config,
        tool_settings=core.logging.tool_settings_config,
        logger=core.logging.logger,
        recorder=core.llm_recorder,
        token_tracker=core.token_tracker,
    )

    # --- Specialized Service Providers ---
    project_planner = providers.Factory(
        ProjectPlanner,
        llm_client=llm_client_manager.provided.get_client.call("planner"),
        logger=core.logging.logger,
    )
    structure_generator = providers.Factory(
        StructureGenerator,
        llm_client=llm_client_manager.provided.get_client.call("prototyper"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
    )
    file_content_generator = providers.Factory(
        FileContentGenerator,
        llm_client=llm_client_manager.provided.get_client.call("prototyper"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
        documentation_manager=core.documentation_manager,
        fragment_cache=core.storage.fragment_cache,
    )
    file_refiner = providers.Factory(
        FileRefiner,
        llm_client=llm_client_manager.provided.get_client.call("coder"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
        documentation_manager=core.documentation_manager,
    )
    file_completeness_checker = providers.Factory(
        FileCompletenessChecker,
        llm_client=llm_client_manager.provided.get_client.call("coder"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
        file_validator=core.storage.file_validator,
        max_retries_per_file=core.logging.tool_settings_config.provided.completeness_checker_max_retries,
    )
    project_reviewer = providers.Factory(
        ProjectReviewer,
        llm_client=llm_client_manager.provided.get_client.call("generalist"),
        logger=core.logging.logger,
    )
    improvement_suggester = providers.Factory(
        ImprovementSuggester,
        llm_client=llm_client_manager.provided.get_client.call("suggester"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
        vulnerability_scanner=core.analysis.vulnerability_scanner,
    )
    improvement_planner = providers.Factory(
        ImprovementPlanner,
        llm_client=llm_client_manager.provided.get_client.call("improvement_planner"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
    )
    test_generator = providers.Factory(
        MultiLanguageTestGenerator,
        llm_client=llm_client_manager.provided.get_client.call("test_generator"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
        command_executor=core.command_executor,
    )
    senior_reviewer = providers.Factory(
        SeniorReviewer,
        llm_client=llm_client_manager.provided.get_client.call("senior_reviewer"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
    )
    structure_pre_reviewer = providers.Factory(
        StructurePreReviewer,
        llm_client=llm_client_manager.provided.get_client.call("senior_reviewer"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
    )
    contingency_planner = providers.Factory(
        ContingencyPlanner,
        client=llm_client_manager.provided.get_client.call("planner"),
        logger=core.logging.logger,
        parser=core.storage.response_parser,
    )
    cicd_healer = providers.Factory(
        CICDHealer,
        logger=core.logging.logger,
        command_executor=core.command_executor,
        llm_client=llm_client_manager.provided.get_client.call("coder"),
    )
    infra_generator = providers.Factory(
        InfraGenerator,
        llm_client=llm_client_manager.provided.get_client.call("prototyper"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
    )

    # --- PhaseContext Provider ---
    phase_context = providers.Singleton(
        PhaseContext,
        config=core.config,
        logger=core.logging.logger,
        ollash_root_dir=core.ollash_root_dir,
        llm_manager=llm_client_manager,
        response_parser=core.storage.response_parser,
        file_manager=core.storage.file_manager,
        file_validator=core.storage.file_validator,
        documentation_manager=core.documentation_manager,
        event_publisher=core.logging.event_publisher,
        code_quarantine=core.analysis.code_quarantine,
        fragment_cache=core.storage.fragment_cache,
        dependency_graph=core.analysis.dependency_graph,
        dependency_scanner=core.analysis.dependency_scanner,
        parallel_generator=core.parallel_generator,
        error_knowledge_base=core.memory.error_knowledge_base,
        policy_enforcer=core.security.policy_enforcer,
        rag_context_selector=core.analysis.rag_context_selector,
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
        generated_projects_dir=core.generated_projects_dir,
        cicd_healer=cicd_healer,
        vulnerability_scanner=core.analysis.vulnerability_scanner,
        export_manager=core.export_manager,
        infra_generator=infra_generator,
        command_executor=core.command_executor,
    )

    project_analysis_phase_factory = providers.Factory(ProjectAnalysisPhase, context=phase_context)

    # --- Phase Providers ---
    phases_list = providers.List(
        # Sprint 10: Phase 0 — clarify before planning
        providers.Factory(ClarificationPhase, context=phase_context),
        providers.Factory(ReadmeGenerationPhase, context=phase_context),
        providers.Factory(StructureGenerationPhase, context=phase_context),
        # Sprint 10: Phase 2.3 — estimate viability before heavy LLM work
        providers.Factory(ViabilityEstimatorPhase, context=phase_context),
        providers.Factory(LogicPlanningPhase, context=phase_context),
        # Sprint 10: Phases 2.6–2.95 — post-planning enrichment
        providers.Factory(TestPlanningPhase, context=phase_context),
        providers.Factory(ComponentTreePhase, context=phase_context),
        providers.Factory(ApiContractPhase, context=phase_context),
        providers.Factory(PlanValidationPhase, context=phase_context),
        providers.Factory(DependencyPrecheckPhase, context=phase_context),
        providers.Factory(InterfaceScaffoldingPhase, context=phase_context),
        providers.Factory(StructurePreReviewPhase, context=phase_context),
        providers.Factory(EmptyFileScaffoldingPhase, context=phase_context),
        providers.Factory(FileContentGenerationPhase, context=phase_context),
        providers.Factory(ChaosInjectionPhase, context=phase_context),
        providers.Factory(FileRefinementPhase, context=phase_context),
        providers.Factory(JavaScriptOptimizationPhase, context=phase_context),
        providers.Factory(VerificationPhase, context=phase_context),
        providers.Factory(CodeQuarantinePhase, context=phase_context),
        providers.Factory(SecurityScanPhase, context=phase_context),
        providers.Factory(LicenseCompliancePhase, context=phase_context),
        providers.Factory(DependencyReconciliationPhase, context=phase_context),
        providers.Factory(TestGenerationExecutionPhase, context=phase_context),
        providers.Factory(WebSmokeTestPhase, context=phase_context),
        providers.Factory(InfrastructureGenerationPhase, context=phase_context),
        providers.Factory(ExhaustiveReviewRepairPhase, context=phase_context),
        providers.Factory(FinalReviewPhase, context=phase_context),
        providers.Factory(CICDHealingPhase, context=phase_context),
        providers.Factory(DocumentationDeployPhase, context=phase_context),
        providers.Factory(IterativeImprovementPhase, context=phase_context),
        providers.Factory(DynamicDocumentationPhase, context=phase_context),
        providers.Factory(ContentCompletenessPhase, context=phase_context),
        providers.Factory(SeniorReviewPhase, context=phase_context),
    )

    auto_agent = providers.Factory(
        AutoAgent,
        kernel=core.logging.agent_kernel,
        llm_manager=llm_client_manager,
        llm_recorder=core.llm_recorder,
        phase_context=phase_context,
        phases=phases_list,
        project_analysis_phase_factory=project_analysis_phase_factory,
    )


# ---------------------------------------------------------------------------
# Domain Agents Container (Agent-per-Domain architecture — additive only)
# ---------------------------------------------------------------------------


class DomainAgentsContainer(containers.DeclarativeContainer):
    """Container for the Agent-per-Domain architecture.

    All providers here are ADDITIVE — no existing providers are modified.
    Wired into ApplicationContainer as ``domain_agents``.
    """

    core = providers.Container(CoreContainer)
    auto_agent_module = providers.Container(AutoAgentContainer)

    # ------------------------------------------------------------------
    # Shared orchestrator infrastructure
    # ------------------------------------------------------------------
    blackboard = providers.Singleton(
        Blackboard,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
    )

    tool_dispatcher = providers.Singleton(
        ToolDispatcher,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        max_batch_size=5,
    )

    self_healing_loop = providers.Singleton(
        SelfHealingLoop,
        error_knowledge_base=core.memory.error_knowledge_base,
        contingency_planner=auto_agent_module.contingency_planner,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        max_retries=2,
    )

    # ------------------------------------------------------------------
    # Domain agents
    # ------------------------------------------------------------------
    architect_agent = providers.Factory(
        ArchitectAgent,
        dependency_graph=core.analysis.dependency_graph,
        structure_generator=auto_agent_module.structure_generator,
        prompt_loader=core.prompt_loader,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        tool_dispatcher=tool_dispatcher,
    )

    # ------------------------------------------------------------------
    # P3 — Sandbox runner (empirical validation via ruff/mypy subprocess)
    # ------------------------------------------------------------------
    sandbox_runner = providers.Singleton(
        SandboxRunner,
        logger=core.logging.logger,
    )

    auditor_agent = providers.Singleton(
        AuditorAgent,
        vulnerability_scanner=core.analysis.vulnerability_scanner,
        code_quarantine=core.analysis.code_quarantine,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        tool_dispatcher=tool_dispatcher,
        sandbox_runner=sandbox_runner,
    )

    devops_agent = providers.Factory(
        DevOpsAgent,
        infra_generator=auto_agent_module.infra_generator,
        cicd_healer=auto_agent_module.cicd_healer,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        tool_dispatcher=tool_dispatcher,
    )

    # Developer agent pool — list of DeveloperAgent instances, one per slot
    developer_agent_pool = providers.Singleton(
        lambda pool_size, file_gen, patcher, locked_fm, par_gen, ep, log, td, shl: [
            DeveloperAgent(
                file_content_generator=file_gen,
                code_patcher=patcher,
                locked_file_manager=locked_fm,
                parallel_file_generator=par_gen,
                event_publisher=ep,
                logger=log,
                tool_dispatcher=td,
                self_healing_loop=shl,
                instance_id=i,
            )
            for i in range(max(1, pool_size))
        ],
        pool_size=3,
        file_gen=auto_agent_module.file_content_generator,
        patcher=providers.Factory(CodePatcher),
        locked_fm=core.storage.file_manager,
        par_gen=core.parallel_generator,
        ep=core.logging.event_publisher,
        log=core.logging.logger,
        td=tool_dispatcher,
        shl=self_healing_loop,
    )

    # ------------------------------------------------------------------
    # P8 — Debate node runner (architect vs auditor by default)
    # ------------------------------------------------------------------
    debate_node_runner = providers.Factory(
        DebateNodeRunner,
        agent_a=architect_agent,
        agent_b=auditor_agent,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
    )

    # ------------------------------------------------------------------
    # P2/P5/P10 — Checkpoint, cost analyser, metrics DB
    # ------------------------------------------------------------------
    checkpoint_manager = providers.Singleton(
        CheckpointManager,
        base_dir=core.ollash_root_dir,
        logger=core.logging.logger,
    )

    cost_analyzer = providers.Singleton(
        CostAnalyzer,
        logger=core.logging.logger,
    )

    metrics_database = providers.Singleton(
        MetricsDatabase,
        db_path=core.ollash_root_dir,
    )

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    domain_agent_orchestrator = providers.Factory(
        DomainAgentOrchestrator,
        architect_agent=architect_agent,
        developer_agent_pool=developer_agent_pool,
        devops_agent=devops_agent,
        auditor_agent=auditor_agent,
        blackboard=blackboard,
        tool_dispatcher=tool_dispatcher,
        self_healing_loop=self_healing_loop,
        locked_file_manager=core.storage.file_manager,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        generated_projects_dir=core.generated_projects_dir,
        # P2/P5/P6/P8/P10 additions
        checkpoint_manager=checkpoint_manager,
        cost_analyzer=cost_analyzer,
        metrics_database=metrics_database,
        debate_node_runner=debate_node_runner,
    )

    # Convenience alias used by blueprints
    orchestrator = domain_agent_orchestrator


# ---------------------------------------------------------------------------
# Application container (top-level)
# ---------------------------------------------------------------------------


class ApplicationContainer(containers.DeclarativeContainer):
    """Top-level container for the entire application."""

    config = providers.Configuration()

    core = providers.Container(CoreContainer, config=config)
    auto_agent_module = providers.Container(AutoAgentContainer, core=core)

    # Agent-per-Domain architecture (additive — does not affect existing providers)
    domain_agents = providers.Container(
        DomainAgentsContainer,
        core=core,
        auto_agent_module=auto_agent_module,
    )


# Instantiate the main container
main_container = ApplicationContainer(config=config.__dict__)
