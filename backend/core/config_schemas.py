from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, PositiveInt, NonNegativeInt


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
    default_model: str = Field(default="ministral-3:8b", description="Default LLM model to use for general tasks.")
    default_timeout: PositiveInt = Field(default=300, description="Default timeout for LLM requests in seconds.")
    default_temperature: float = Field(default=0.5, ge=0.0, le=1.0, description="Default temperature for LLM generation.")
    
    # Specific model assignments
    coding: Optional[str] = Field(None, description="Model for coding tasks.")
    reasoning: Optional[str] = Field(None, description="Model for reasoning tasks.")
    orchestration: Optional[str] = Field(None, description="Model for orchestration tasks.")
    summarization: Optional[str] = Field(None, description="Model for summarization tasks.")
    self_correction: Optional[str] = Field(None, description="Model for self-correction tasks.")
    embedding: Optional[str] = Field(None, description="Model for embedding generation.")

    # Auto Agent specific model assignments and timeouts
    prototyper_model: Optional[str] = None
    coder_model_auto: Optional[str] = Field(None, alias="coder_model") # Using alias for existing config
    planner_model: Optional[str] = None
    generalist_model: Optional[str] = None
    suggester_model: Optional[str] = None
    improvement_planner_model: Optional[str] = None
    senior_reviewer_model: Optional[str] = None

    prototyper_timeout: Optional[PositiveInt] = Field(None, alias="prototyper")
    coder_timeout: Optional[PositiveInt] = Field(None, alias="coder")
    planner_timeout: Optional[PositiveInt] = Field(None, alias="planner")
    generalist_timeout: Optional[PositiveInt] = Field(None, alias="generalist")
    suggester_timeout: Optional[PositiveInt] = Field(None, alias="suggester")
    improvement_planner_timeout: Optional[PositiveInt] = Field(None, alias="improvement_planner")
    senior_reviewer_timeout: Optional[PositiveInt] = Field(None, alias="senior_reviewer")
    
    embedding_cache_settings: EmbeddingCacheConfig = Field(default_factory=EmbeddingCacheConfig, alias="embedding_cache") # NEW
    
    # Allow extra fields for flexibility, but warn
    class Config:
        extra = "allow"


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
    supported_types: List[str] = ["report", "diagram", "checklist", "code", "comparison"]
    mermaid_theme: str = "default"

class OCRConfig(BaseModel):
    model: str = "deepseek-ocr:3b"
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    enabled: bool = False

class SpeechConfig(BaseModel):
    enabled: bool = False
    language: str = "es-ES"
    max_duration_seconds: PositiveInt = 60

class AgentFeaturesConfig(BaseModel):
    cross_reference: bool = Field(False, description="Enable cross-referencing features.")
    artifacts_panel: bool = Field(False, description="Enable artifacts panel in UI.")
    feedback_refinement: bool = Field(False, description="Enable feedback-based refinement.")
    multimodal_ingestion: bool = Field(False, description="Enable multimodal input ingestion.")
    ocr_enabled: bool = Field(False, description="Enable Optical Character Recognition (OCR).")
    speech_enabled: bool = Field(False, description="Enable speech input/output.")

    # Nested configurations
    knowledge_graph_settings: KnowledgeGraphConfig = Field(default_factory=KnowledgeGraphConfig, alias="knowledge_graph")
    decision_context_settings: DecisionContextConfig = Field(default_factory=DecisionContextConfig, alias="decision_context")
    artifacts_settings: ArtifactsConfig = Field(default_factory=ArtifactsConfig, alias="artifacts")
    ocr_settings: OCRConfig = Field(default_factory=OCRConfig, alias="ocr")
    speech_settings: SpeechConfig = Field(default_factory=SpeechConfig, alias="speech")

    class Config:
        extra = "allow"
        populate_by_name = True # Allow using aliases for field names

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
    sandbox_level: Literal["limited", "full", "none"] = Field("limited", alias="sandbox", description="Security sandbox level for command execution.")
    max_context_tokens: PositiveInt = Field(8000, description="Maximum tokens for LLM context window.")
    summarize_threshold_ratio: float = Field(0.7, ge=0.0, le=1.0, description="Ratio of max_context_tokens at which summarization is triggered.")
    history_limit: NonNegativeInt = Field(20, description="Maximum number of conversation turns to keep in memory.")
    log_level: str = Field("debug", description="Logging level (e.g., 'debug', 'info', 'warning', 'error').")
    log_file: str = Field("ollash.log", description="Default log file name.")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Logging format string.")
    default_system_prompt_path: str = Field("prompts/orchestrator/default_orchestrator.json", description="Path to the default system prompt.")
    use_docker_sandbox: bool = Field(False, description="Whether to use Docker for sandbox execution.")

    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    gpu_rate_limiter: GPUAwareRateLimiterConfig = Field(default_factory=GPUAwareRateLimiterConfig)

    # AutoAgent specific settings for iteration and refinement
    auto_confirm_tools: bool = Field(False, description="Automatically confirm state-modifying tool executions.")
    max_iterations: PositiveInt = Field(30, description="Maximum iterations for agent loops.")
    loop_detection_threshold: PositiveInt = Field(3, description="Number of similar actions to trigger loop detection.")
    semantic_similarity_threshold: float = Field(0.95, ge=0.0, le=1.0, description="Semantic similarity threshold for loop detection.")
    parallel_generation_max_concurrent: PositiveInt = Field(3, description="Max concurrent file generations.")
    parallel_generation_max_rpm: PositiveInt = Field(10, description="Max requests per minute for parallel generation.")
    senior_review_max_attempts: PositiveInt = Field(3, description="Max attempts for senior review fixes.")
    completeness_checker_max_retries: PositiveInt = Field(2, description="Max retries for file completeness checks.")
    token_encoding_name: str = Field("cl100k_base", description="Encoding name for token counting (e.g., 'cl100k_base').")

    # Ollama API retry settings
    ollama_retries: PositiveInt = Field(5, description="Max retries for Ollama API calls.")
    ollama_backoff_factor: float = Field(1.0, description="Backoff factor for Ollama API call retries.")
    ollama_retry_status_forcelist: List[int] = Field([429, 500, 502, 503, 504], description="HTTP status codes that trigger retries for Ollama API calls.")


    class Config:
        extra = "allow"
        populate_by_name = True
