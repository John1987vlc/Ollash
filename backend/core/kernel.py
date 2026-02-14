import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Type, TypeVar, Union
from pydantic import BaseModel, ValidationError, HttpUrl
from collections import defaultdict
import uuid # For correlation IDs
import logging # Needed for the temporary logger

# Centralized config object
from backend.core.config import get_config

from backend.utils.core.agent_logger import AgentLogger # This is now the wrapper
from backend.utils.core.structured_logger import StructuredLogger, set_correlation_id # NEW
from backend.core.config_schemas import (
    LLMModelsConfig,
    AgentFeaturesConfig,
    ToolSettingsConfig,
)

T = TypeVar('T', bound=BaseModel)

class ConfigLoader:
    """
    Loads, merges, and validates configuration from the central config object.
    Stores validated configuration as Pydantic models.
    """
    def __init__(self, logger: AgentLogger): # Logger is now AgentLogger
        self._logger = logger
        self._loaded_configs: Dict[str, BaseModel] = {}
        self._raw_config_data: Dict[str, Any] = {}
        
        self._config_map: Dict[str, Type[BaseModel]] = {
            "llm_models": LLMModelsConfig,
            "agent_features": AgentFeaturesConfig,
            "tool_settings": ToolSettingsConfig,
        }
        self._load_and_validate_all_configs()

    def _load_and_validate_all_configs(self):
        """Loads data from the central config and validates it."""
        self._logger.info("Loading configuration from central config object.")

        # Get the latest config instance
        current_config = get_config()

        # Populate raw config data from the imported central_config object
        self._raw_config_data = {
            "llm_models": current_config.LLM_MODELS or {},
            "agent_features": current_config.AGENT_FEATURES or {},
            "tool_settings": current_config.TOOL_SETTINGS or {},
        }

        # Validate against Pydantic schemas
        try:
            self._loaded_configs["llm_models"] = LLMModelsConfig.model_validate(self._raw_config_data.get("llm_models", {}))
            self._loaded_configs["agent_features"] = AgentFeaturesConfig.model_validate(self._raw_config_data.get("agent_features", {}))
            self._loaded_configs["tool_settings"] = ToolSettingsConfig.model_validate(self._raw_config_data.get("tool_settings", {}))
            self._logger.info("All configurations loaded and validated successfully.")
        except ValidationError as e:
            self._logger.error(f"Configuration validation failed: {e.errors()}")
            raise RuntimeError(f"Invalid configuration: {e}")
        except Exception as e:
            self._logger.error(f"An unexpected error occurred during config loading or validation: {e}")
            raise RuntimeError(f"Configuration error: {e}")

    def get_config(self, config_type: str) -> Optional[BaseModel]:
        """Returns a validated Pydantic config model by type."""
        return self._loaded_configs.get(config_type)
    
    def get_raw_config_data(self) -> Dict[str, Any]:
        """Returns the raw, merged (but not Pydantic-validated) config data."""
        return self._raw_config_data


class AgentKernel:
    """
    The lightweight core kernel for the agent system.
    This class loads configuration, sets up logging, and provides core services.
    """
    def __init__(self, ollash_root_dir: Optional[Path] = None):
        self.ollash_root_dir = ollash_root_dir if ollash_root_dir else Path(os.getcwd())
        
        # --- Initialize Configuration FIRST ---
        # Use a temporary standard logger for initial config loading errors, if any,
        # before the StructuredLogger is fully set up.
        temp_agent_logger = AgentLogger(structured_logger=StructuredLogger(log_file_path=self.ollash_root_dir / "logs" / "temp_kernel_init.log", logger_name="TempKernelInit"), logger_name="TempAgentKernelWrapper")
        
        # Instantiate ConfigLoader with the temporary logger
        self._config_loader = ConfigLoader(temp_agent_logger)

        # Get tool settings for structured logger configuration
        tool_settings_config_model = self._config_loader.get_config("tool_settings")
        if not tool_settings_config_model:
            raise RuntimeError("Tool settings configuration not loaded. Cannot initialize structured logger.")
        tool_settings: ToolSettingsConfig = tool_settings_config_model # type: ignore
        if not tool_settings:
            raise RuntimeError("Tool settings configuration not loaded. Cannot initialize structured logger.")

        # --- Initialize Structured Logger ---
        log_file_name = tool_settings.log_file
        log_level = tool_settings.log_level
        log_file_path = self.ollash_root_dir / "logs" / log_file_name
        
        self._structured_logger = StructuredLogger(
            log_file_path=log_file_path,
            logger_name="Ollash", # Master logger name
            log_level=log_level
        )
        # Replace the temporary logger in ConfigLoader with the real one
        self._config_loader._logger = AgentLogger(structured_logger=self._structured_logger, logger_name="ConfigLoader")

        # --- Initialize AgentLogger Wrapper ---
        self._agent_logger = AgentLogger(structured_logger=self._structured_logger, logger_name="AgentKernel")
        self._agent_logger.info("AgentKernel initialized successfully with modular configuration and structured logging.")

    def get_logger(self) -> AgentLogger:
        """Returns the AgentLogger instance for this kernel."""
        return self._agent_logger

    def get_llm_models_config(self) -> LLMModelsConfig:
        """Returns the validated LLM models configuration."""
        config = self._config_loader.get_config("llm_models")
        if not config:
            raise RuntimeError("LLM models configuration not loaded.")
        return config # type: ignore

    def get_agent_features_config(self) -> AgentFeaturesConfig:
        """Returns the validated agent features configuration."""
        config = self._config_loader.get_config("agent_features")
        if not config:
            raise RuntimeError("Agent features configuration not loaded.")
        return config # type: ignore

    def get_tool_settings_config(self) -> ToolSettingsConfig:
        """Returns the validated tool settings configuration."""
        config = self._config_loader.get_config("tool_settings")
        if not config:
            raise RuntimeError("Tool settings configuration not loaded.")
        return config # type: ignore
    
    def get_full_config(self) -> Dict[str, Any]:
        """Returns the full raw, merged configuration as a dictionary."""
        # Access the raw data from ConfigLoader (not Pydantic models for full raw)
        return self._config_loader._raw_config_data

    def start_interaction_context(self) -> str:
        """Generates a unique correlation ID and sets it for the current thread."""
        new_id = str(uuid.uuid4())
        set_correlation_id(new_id)
        self.get_logger().info("Interaction context started.", extra={"event_type": "interaction_start", "correlation_id": new_id})
        return new_id

    def end_interaction_context(self, correlation_id: str, status: str = "completed"):
        """Ends the interaction context for the current thread."""
        self.get_logger().info(f"Interaction context ended: {status}.", extra={"event_type": "interaction_end", "correlation_id": correlation_id, "status": status})
        set_correlation_id(None) # Clear the correlation ID