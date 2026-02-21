import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from backend.core.config_schemas import AgentFeaturesConfig, LLMModelsConfig, ToolSettingsConfig
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger, set_correlation_id

# Import the newly separated ConfigLoader
from .config_loader import ConfigLoader


class AgentKernel:
    """
    The lightweight core kernel for the agent system.
    This class loads configuration, sets up logging, and provides core services.
    """

    def __init__(
        self,
        ollash_root_dir: Optional[Path] = None,
        structured_logger: Optional[StructuredLogger] = None,
    ):
        self.ollash_root_dir = ollash_root_dir if ollash_root_dir else Path(os.getcwd())

        # If a structured logger isn't provided, create a default one.
        if structured_logger:
            self._structured_logger = structured_logger
        else:
            log_dir = self.ollash_root_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            self._structured_logger = StructuredLogger(log_file_path=log_dir / "kernel.log")

        # The kernel's own logger and the config loader's logger both use the same underlying structured logger.
        self._agent_logger = AgentLogger(structured_logger=self._structured_logger, logger_name="AgentKernel")
        config_loader_logger = AgentLogger(structured_logger=self._structured_logger, logger_name="ConfigLoader")

        # Instantiate ConfigLoader
        self._config_loader = ConfigLoader(config_loader_logger)

        self._agent_logger.info("AgentKernel initialized.")

    def get_logger(self) -> AgentLogger:
        """Returns the AgentLogger instance for this kernel."""
        return self._agent_logger

    def get_llm_models_config(self) -> LLMModelsConfig:
        """Returns the validated LLM models configuration."""
        config = self._config_loader.get_config("llm_models")
        if not isinstance(config, LLMModelsConfig):
            raise RuntimeError("LLM models configuration not loaded or is of incorrect type.")
        return config

    def get_agent_features_config(self) -> AgentFeaturesConfig:
        """Returns the validated agent features configuration."""
        config = self._config_loader.get_config("agent_features")
        if not isinstance(config, AgentFeaturesConfig):
            raise RuntimeError("Agent features configuration not loaded or is of incorrect type.")
        return config

    def get_tool_settings_config(self) -> ToolSettingsConfig:
        """Returns the validated tool settings configuration."""
        config = self._config_loader.get_config("tool_settings")
        if not isinstance(config, ToolSettingsConfig):
            raise RuntimeError("Tool settings configuration not loaded or is of incorrect type.")
        return config

    def get_full_config(self) -> Dict[str, Any]:
        """Returns the full raw, merged configuration as a dictionary."""
        return self._config_loader.get_raw_config_data()

    def start_interaction_context(self) -> str:
        """Generates a unique correlation ID and sets it for the current thread."""
        new_id = str(uuid.uuid4())
        set_correlation_id(new_id)
        self.get_logger().info(
            "Interaction context started.",
            extra={"event_type": "interaction_start", "correlation_id": new_id},
        )
        return new_id

    def end_interaction_context(self, correlation_id: str, status: str = "completed"):
        """Ends the interaction context for the current thread."""
        self.get_logger().info(
            f"Interaction context ended: {status}.",
            extra={
                "event_type": "interaction_end",
                "correlation_id": correlation_id,
                "status": status,
            },
        )
        set_correlation_id(None)  # Clear the correlation ID
