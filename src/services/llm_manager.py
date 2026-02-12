from typing import Dict, List, Tuple, Optional, Any
import os
import json
from pathlib import Path

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.benchmark_model_selector import AutoModelSelector, BenchmarkDatabase
from src.utils.core.concurrent_rate_limiter import SessionResourceManager
from src.utils.core.model_health_monitor import ModelHealthMonitor
from src.utils.core.llm_recorder import LLMRecorder # NEW
from src.core.config_schemas import LLMModelsConfig, ToolSettingsConfig


class LLMClientManager:
    """
    Manages the provisioning and lifecycle of OllamaClient instances for various LLM roles.
    This class centralizes the logic for selecting models, applying benchmarks, and
    integrating with rate limiting and health monitoring.
    """

    # Common LLM roles and their default models/timeouts
    LLM_ROLES = [
        ("prototyper", "prototyper_model", "gpt-oss:20b", 600),
        ("coder", "coder_model", "qwen3-coder:30b", 480),
        ("planner", "planner_model", "ministral-3:14b", 900),
        ("generalist", "generalist_model", "ministral-3:8b", 300),
        ("suggester", "suggester_model", "ministral-3:8b", 300),
        ("improvement_planner", "improvement_planner_model", "ministral-3:14b", 900),
        ("test_generator", "test_generator_model", "qwen3-coder:30b", 480),
        ("senior_reviewer", "senior_reviewer_model", "ministral-3:14b", 900),
        ("orchestration", "orchestration_model", "ministral-3:8b", 300),
        ("analyst", "analyst_model", "ministral-3:14b", 600),
        ("writer", "writer_model", "ministral-3:8b", 450),
        ("default", "default_model", "qwen3-coder-next:14b", 600),
    ]

    def __init__(
        self,
        config: LLMModelsConfig, # Changed from Dict to LLMModelsConfig
        tool_settings_config: ToolSettingsConfig, # NEW
        logger: AgentLogger,
        ollash_root_dir: Path,
        session_resource_manager: SessionResourceManager,
        benchmark_selector: AutoModelSelector,
        llm_recorder: LLMRecorder,
        model_health_monitor: Optional[ModelHealthMonitor] = None,
    ):
        self.config = config
        self.tool_settings_config = tool_settings_config
        self.logger = logger
        self.ollash_root_dir = ollash_root_dir
        self.session_resource_manager = session_resource_manager
        self.benchmark_selector = benchmark_selector
        self.model_health_monitor = model_health_monitor
        self._llm_recorder = llm_recorder
        self.ollama_url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            self.config.ollama_url, # Changed from .get("ollama_url", ...)
        )
        self.llm_clients: Dict[str, OllamaClient] = {}
        self._initialize_llm_clients()

    def _initialize_llm_clients(self):
        """Create OllamaClient instances for each specialized LLM role.

        Uses BenchmarkModelSelector for auto-optimization if benchmark data exists,
        otherwise falls back to configured defaults.
        """
        # Try to integrate benchmark results for model optimization
        optimized_config = self.benchmark_selector.generate_optimized_config(self.config.model_dump())
        if optimized_config:
            self.logger.info("🎯 Applying benchmark-optimized model configuration")
            # Optimized config is a dict, so it uses .get()
            # We assume it provides keys matching our LLM_ROLES model_key convention
            # e.g., {"prototyper_model": "optimized-prototyper"}
            pass # We'll handle applying optimized config in the loop below

        for role, model_key_attr, default_model, default_timeout in self.LLM_ROLES:
            # Dynamically get model and timeout from self.config or optimized_config
            model = getattr(self.config, model_key_attr, default_model)
            timeout_attr = f"{role}_timeout" # e.g., "prototyper_timeout"
            timeout = getattr(self.config, timeout_attr, default_timeout)

            # Apply optimized model if available
            if optimized_config and model_key_attr in optimized_config:
                model = optimized_config[model_key_attr]
                self.logger.debug(f"  Override {role} model with optimized: {model}")
            # Apply optimized timeout if available (if any such key exists in optimized_config)
            if optimized_config and timeout_attr in optimized_config:
                timeout = optimized_config[timeout_attr]
                self.logger.debug(f"  Override {role} timeout with optimized: {timeout}")

            # Create a consolidated config dictionary for OllamaClient
            ollama_client_config_dict = {
                "ollama_max_retries": self.tool_settings_config.ollama_retries,
                "ollama_backoff_factor": self.tool_settings_config.ollama_backoff_factor,
                "ollama_retry_status_forcelist": self.tool_settings_config.ollama_retry_status_forcelist,
                "rate_limiting": self.tool_settings_config.rate_limiting.model_dump(),
                "gpu_rate_limiter": self.tool_settings_config.gpu_rate_limiter.model_dump(),
                "models": {
                    "default": self.config.default_model,
                    "coding": self.config.coding,
                    "reasoning": self.config.reasoning,
                    "orchestration": self.config.orchestration,
                    "summarization": self.config.summarization,
                    "self_correction": self.config.self_correction,
                    "embedding": self.config.embedding,
                    "prototyper": self.config.prototyper_model,
                    "coder": self.config.coder_model_auto,
                    "planner": self.config.planner_model,
                    "generalist": self.config.generalist_model,
                    "suggester": self.config.suggester_model,
                    "improvement_planner": self.config.improvement_planner_model,
                    "senior_reviewer": self.config.senior_reviewer_model,
                    # Add other models as needed, handling Optional[str]
                },
                "embedding": self.config.embedding,
                "embedding_cache": self.config.embedding_cache_settings.model_dump(),
                "project_root": self.ollash_root_dir,
                "ollama_embedding_model": self.config.embedding,
            }

            self.llm_clients[role] = OllamaClient(
                url=self.ollama_url,
                model=model,
                timeout=timeout,
                logger=self.logger,
                config=ollama_client_config_dict,
                llm_recorder=self._llm_recorder,
                model_health_monitor=self.model_health_monitor,
            )
            self.logger.info(f"  {role:20} → {str(model or 'N/A'):30} (timeout: {str(timeout or 'N/A')}s)")

        self.logger.info("LLMClientManager: All specialized Ollama clients initialized.")

    def get_client(self, role: str) -> Optional[OllamaClient]:
        """
        Retrieves the OllamaClient instance for a given role.
        """
        if role not in self.llm_clients:
            self.logger.warning(f"Requested LLM client for role '{role}' not found.")
            return None
        return self.llm_clients[role]

    def get_all_clients(self) -> Dict[str, OllamaClient]:
        """
        Returns a dictionary of all initialized OllamaClient instances.
        """
        return self.llm_clients