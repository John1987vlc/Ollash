from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, NonNegativeInt, PositiveInt


# --- Embedding Cache Configuration Schema ---
class EmbeddingCacheConfig(BaseModel):
    max_size: PositiveInt = Field(10000, description="Maximum number of embeddings to store in cache.")
    ttl_seconds: PositiveInt = Field(3600, description="Time-to-live for cache entries in seconds.")
    persist_to_disk: bool = Field(True, description="Whether to persist the embedding cache to disk.")


# --- LLM Models Configuration Schema ---
class LLMModelDefinition(BaseModel):
    name: str
    default: Optional[str] = None
    timeout: Optional[PositiveInt] = None


class LLMModelsConfig(BaseModel):
    ollama_url: HttpUrl = Field(default="http://localhost:11434", description="Base URL for the Ollama server.")
    default_model: str = Field(
        default="mistral:latest",
        description="Default LLM model to use for general tasks.",
    )
    default_temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default temperature for LLM generation.",
    )

    # NEW: Flexible role-to-model mapping
    agent_roles: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of agent roles (e.g., 'planner', 'coder') to specific model names.",
    )

    # Deprecated fields for specific tasks are removed in favor of agent_roles

    embedding: Optional[str] = Field(None, description="Model for embedding generation.")
    embedding_cache_settings: EmbeddingCacheConfig = Field(
        default_factory=EmbeddingCacheConfig, alias="embedding_cache"
    )

    # Vision model for multimodal analysis
    vision_model: Optional[str] = Field(None, description="Model for image/vision analysis (e.g., llava).")

    default_timeout: PositiveInt = Field(300, description="Default timeout for LLM API calls in seconds.")

    # Multi-provider configuration
    providers: List["ExternalProviderConfig"] = Field(
        default_factory=list,
        description="Additional LLM providers (Groq, Together, OpenRouter, etc.).",
    )

    class Config:
        extra = "allow"


class ExternalProviderConfig(BaseModel):
    """Configuration for an external LLM provider."""

    name: str = Field(description="Provider name (e.g., 'groq', 'together').")
    type: Literal["ollama", "openai_compatible"] = Field("openai_compatible", description="Provider type.")
    base_url: str = Field(description="Provider API base URL.")
    api_key: Optional[str] = Field(None, description="API key for authentication.")
    models: Dict[str, str] = Field(
        default_factory=dict,
        description="Role-to-model mapping for this provider.",
    )
    timeout: PositiveInt = Field(120, description="Request timeout in seconds.")


# --- Agent Features Configuration Schema ---
class KnowledgeGraphConfig(BaseModel):
    auto_build: bool = True
    max_depth: NonNegativeInt = 3
    similarity_threshold: float = Field(0.6, ge=0.0, le=1.0)


class DecisionContextConfig(BaseModel):
    auto_record: bool = False
    save_on_shutdown: bool = True
    retention_days: NonNegativeInt = 365


class ArtifactsConfig(BaseModel):
    max_diagram_size: str = "1000x800"
    supported_types: List[str] = [
        "report",
        "diagram",
        "checklist",
        "code",
        "comparison",
    ]
    mermaid_theme: str = "default"


class OCRConfig(BaseModel):
    model: str = "deepseek-ocr:3b"
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    enabled: bool = False


class SpeechConfig(BaseModel):
    enabled: bool = False
    language: str = "es-ES"
    max_duration_seconds: PositiveInt = 60


class InfraConfig(BaseModel):
    cloud: str = Field("aws", description="Default cloud provider for IaC generation.")
    container_orchestrator: str = Field("kubernetes", description="Default container orchestrator.")


class AgentFeaturesConfig(BaseModel):
    cross_reference: bool = Field(False, description="Enable cross-referencing features.")
    artifacts_panel: bool = Field(False, description="Enable artifacts panel in UI.")
    feedback_refinement: bool = Field(False, description="Enable feedback-based refinement.")
    multimodal_ingestion: bool = Field(False, description="Enable multimodal input ingestion.")
    ocr_enabled: bool = Field(False, description="Enable Optical Character Recognition (OCR).")
    speech_enabled: bool = Field(False, description="Enable speech input/output.")

    # --- New feature flags ---
    refactoring_enabled: bool = Field(False, description="Enable proactive SOLID refactoring agent.")
    ui_analysis_enabled: bool = Field(False, description="Enable multimodal UI/UX analysis.")
    cicd_auto_healing: bool = Field(False, description="Enable CI/CD auto-healing capabilities.")
    load_testing_enabled: bool = Field(False, description="Enable load simulation and app benchmarking.")
    license_scanning_deep: bool = Field(False, description="Enable deep license compatibility scanning.")
    prompt_auto_tuning: bool = Field(False, description="Enable automatic prompt optimization from feedback.")
    project_license: str = Field("MIT", description="Default license type for generated projects.")
    documentation_languages: List[str] = Field(
        default_factory=lambda: ["en"],
        description="Languages for documentation translation.",
    )

    # Nested configurations
    knowledge_graph_settings: KnowledgeGraphConfig = Field(
        default_factory=KnowledgeGraphConfig, alias="knowledge_graph"
    )
    decision_context_settings: DecisionContextConfig = Field(
        default_factory=DecisionContextConfig, alias="decision_context"
    )
    artifacts_settings: ArtifactsConfig = Field(default_factory=ArtifactsConfig, alias="artifacts")
    ocr_settings: OCRConfig = Field(default_factory=OCRConfig, alias="ocr")
    speech_settings: SpeechConfig = Field(default_factory=SpeechConfig, alias="speech")
    infra_settings: InfraConfig = Field(default_factory=InfraConfig, alias="infrastructure")

    class Config:
        extra = "allow"
        populate_by_name = True  # Allow using aliases for field names


# --- Benchmark Configuration Schema ---
class BenchmarkConfig(BaseModel):
    """Configuration for benchmark and continuous learning features."""

    shadow_evaluation_enabled: bool = Field(False, description="Enable shadow evaluation during pipeline runs.")
    shadow_critic_threshold: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Correction rate threshold to flag a model as underperforming.",
    )
    phase_failure_db_dir: str = Field(
        ".cache/phase_failures",
        description="Directory for phase failure database storage.",
    )
    phase_failure_threshold: PositiveInt = Field(
        3, description="Number of failures before marking model unsuitable for a phase."
    )
    cost_efficiency_weight: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Weight of cost-efficiency in model selection (vs raw quality).",
    )
    rubric_evaluation_enabled: bool = Field(
        True, description="Enable multidimensional rubric evaluation in benchmarks."
    )
    shadow_log_dir: str = Field(
        ".cache/shadow_logs",
        description="Directory for shadow evaluation logs.",
    )


# --- Tool Settings Configuration Schema ---
class RateLimitingConfig(BaseModel):
    requests_per_minute: PositiveInt = 60
    max_tokens_per_minute: PositiveInt = 100000


class GPUAwareRateLimiterConfig(BaseModel):
    degradation_threshold_ms: float = 5000.0
    recovery_threshold_ms: float = 2000.0
    min_rpm: PositiveInt = 5
    ema_alpha: float = Field(0.3, ge=0.0, le=1.0)


class ToolSettingsConfig(BaseModel):
    sandbox_level: Literal["limited", "full", "none"] = Field(
        "limited",
        alias="sandbox",
        description="Security sandbox level for command execution.",
    )
    max_context_tokens: PositiveInt = Field(8000, description="Maximum tokens for LLM context window.")
    summarize_threshold_ratio: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Ratio of max_context_tokens at which summarization is triggered.",
    )
    history_limit: NonNegativeInt = Field(20, description="Maximum number of conversation turns to keep in memory.")
    log_level: str = Field(
        "debug",
        description="Logging level (e.g., 'debug', 'info', 'warning', 'error').",
    )
    log_file: str = Field("ollash.log", description="Default log file name.")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Logging format string.",
    )
    default_system_prompt_path: str = Field(
        "prompts/orchestrator/default_orchestrator.json",
        description="Path to the default system prompt.",
    )
    use_docker_sandbox: bool = Field(False, description="Whether to use Docker for sandbox execution.")

    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    gpu_rate_limiter: GPUAwareRateLimiterConfig = Field(default_factory=GPUAwareRateLimiterConfig)

    # AutoAgent specific settings for iteration and refinement
    auto_confirm_tools: bool = Field(False, description="Automatically confirm state-modifying tool executions.")
    max_iterations: PositiveInt = Field(30, description="Maximum iterations for agent loops.")
    loop_detection_threshold: PositiveInt = Field(3, description="Number of similar actions to trigger loop detection.")
    semantic_similarity_threshold: float = Field(
        0.95,
        ge=0.0,
        le=1.0,
        description="Semantic similarity threshold for loop detection.",
    )
    parallel_generation_max_concurrent: PositiveInt = Field(3, description="Max concurrent file generations.")
    parallel_generation_max_rpm: PositiveInt = Field(10, description="Max requests per minute for parallel generation.")
    senior_review_max_attempts: PositiveInt = Field(3, description="Max attempts for senior review fixes.")
    completeness_checker_max_retries: PositiveInt = Field(2, description="Max retries for file completeness checks.")
    token_encoding_name: str = Field(
        "cl100k_base",
        description="Encoding name for token counting (e.g., 'cl100k_base').",
    )

    # Ollama API retry settings
    ollama_retries: PositiveInt = Field(5, description="Max retries for Ollama API calls.")
    ollama_backoff_factor: float = Field(1.0, description="Backoff factor for Ollama API call retries.")
    ollama_retry_status_forcelist: List[int] = Field(
        [429, 500, 502, 503, 504],
        description="HTTP status codes that trigger retries for Ollama API calls.",
    )

    # Missing attributes from tests
    git_auto_confirm_lines_threshold: PositiveInt = Field(
        5, description="Lines threshold for auto-confirming git operations."
    )
    auto_confirm_minor_git_commits: bool = Field(False, description="Automatically confirm minor git commits.")
    write_auto_confirm_lines_threshold: PositiveInt = Field(
        10, description="Lines threshold for auto-confirming write operations."
    )
    auto_confirm_minor_writes: bool = Field(False, description="Automatically confirm minor file writes.")
    critical_paths_patterns: List[str] = Field(
        default_factory=list,
        description="List of glob patterns for critical paths requiring explicit confirmation.",
    )

    # --- New feature settings ---
    parallel_generation_enabled: bool = Field(False, description="Enable multi-agent parallel generation.")
    parallel_agent_count: PositiveInt = Field(2, description="Number of parallel agent instances for generation.")
    checkpoint_enabled: bool = Field(True, description="Enable checkpoint persistence for AutoAgent phases.")
    checkpoint_dir: str = Field(".cache/checkpoints", description="Directory for checkpoint storage.")
    security_scanning_enabled: bool = Field(True, description="Enable real-time vulnerability scanning.")
    block_on_critical: bool = Field(True, description="Block code generation on critical vulnerabilities.")
    cost_tracking_enabled: bool = Field(True, description="Enable model cost tracking and analysis.")
    wasm_sandbox_enabled: bool = Field(False, description="Enable WebAssembly sandbox for test execution.")
    wasm_runtime: str = Field("wasmtime", description="WebAssembly runtime to use (wasmtime or wasmer).")
    plugins_dir: str = Field("plugins", description="Directory for third-party plugins.")
    enabled_plugins: List[str] = Field(default_factory=list, description="List of enabled plugin IDs.")

    # Benchmark and continuous learning
    benchmark: BenchmarkConfig = Field(default_factory=BenchmarkConfig)

    class Config:
        extra = "allow"
        populate_by_name = True
