"""Dependency Injection containers for the Ollash application."""

from pathlib import Path

from dependency_injector import containers, providers

from backend.agents.auto_agent import AutoAgent
from backend.agents.auto_agent_with_tools import AutoAgentWithTools

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
from backend.utils.domains.auto_generation.planning.contingency_planner import ContingencyPlanner
from backend.utils.domains.auto_generation.generation.enhanced_file_content_generator import (
    EnhancedFileContentGenerator,
)
from backend.utils.domains.auto_generation.generation.infra_generator import InfraGenerator
from backend.utils.domains.auto_generation.generation.structure_generator import StructureGenerator
from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher

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
    """Container for the new 8-phase AutoAgent pipeline.

    Keeps only the providers that:
    1. AutoAgent itself needs (llm_client_manager, file_manager, event_publisher, logger)
    2. DomainAgentsContainer still uses (structure_generator, contingency_planner,
       infra_generator, cicd_healer, file_content_generator)
    """

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

    # --- Providers kept for DomainAgentsContainer backward compatibility ---
    structure_generator = providers.Factory(
        StructureGenerator,
        llm_client=llm_client_manager.provided.get_client.call("prototyper"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
    )
    file_content_generator = providers.Factory(
        EnhancedFileContentGenerator,
        llm_client=llm_client_manager.provided.get_client.call("prototyper"),
        logger=core.logging.logger,
        response_parser=core.storage.response_parser,
        documentation_manager=core.documentation_manager,
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

    # --- AutoAgent (new 8-phase pipeline, 5 simple constructor args) ---
    auto_agent = providers.Factory(
        AutoAgent,
        llm_manager=llm_client_manager,
        file_manager=core.storage.file_manager,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        generated_projects_dir=core.generated_projects_dir,
    )

    # --- AutoAgentWithTools (tool-calling preview, qwen3.5:9b) ---
    auto_agent_with_tools = providers.Factory(
        AutoAgentWithTools,
        llm_manager=llm_client_manager,
        file_manager=core.storage.file_manager,
        event_publisher=core.logging.event_publisher,
        logger=core.logging.logger,
        generated_projects_dir=core.generated_projects_dir,
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
