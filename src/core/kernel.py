import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Type, TypeVar, Union
from pydantic import BaseModel, ValidationError, HttpUrl
from collections import defaultdict
import uuid # For correlation IDs
import logging # Needed for the temporary logger

from src.utils.core.agent_logger import AgentLogger # This is now the wrapper
from src.utils.core.structured_logger import StructuredLogger, set_correlation_id # NEW
from src.core.config_schemas import (
    LLMModelsConfig,
    AgentFeaturesConfig,
    ToolSettingsConfig,
)

T = TypeVar('T', bound=BaseModel)

class ConfigLoader:
    """
    Loads, merges, and validates configuration from multiple JSON files and environment variables.
    Stores validated configuration as Pydantic models.
    """
    def __init__(self, config_dir: Path, logger: AgentLogger): # Logger is now AgentLogger
        self._config_dir = config_dir
        self._logger = logger
        self._loaded_configs: Dict[str, BaseModel] = {}
        self._raw_config_data: Dict[str, Any] = {}
        
        self._config_map: Dict[str, Type[BaseModel]] = {
            "llm_models.json": LLMModelsConfig,
            "agent_features.json": AgentFeaturesConfig,
            "tool_settings.json": ToolSettingsConfig,
        }
        self._load_and_validate_all_configs()

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Loads a single JSON configuration file."""
        if not file_path.exists():
            self._logger.info(f"Optional config file not found: {file_path}. Skipping.")
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self._logger.warning(f"Error loading config file {file_path}: {e}. Skipping this file.")
            return {}
        except Exception as e:
            self._logger.error(f"Unexpected error with config file {file_path}: {e}. Skipping this file.")
            return {}

    def _merge_configs(self, base_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merges two dictionaries."""
        merged = base_config.copy()
        for k, v in new_config.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = self._merge_configs(merged[k], v)
            else:
                merged[k] = v
        return merged

    def _apply_env_variables(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Applies environment variables to override config values (flat for now)."""
        # This is a simplified approach. A more robust solution might map env vars to nested fields.
        for key, value in os.environ.items():
            # Example: OLLASH_OLLAMA_URL -> ollama_url
            normalized_key = key.lower().replace("ollash_", "")
            if normalized_key in config_data:
                # Attempt to cast env var to appropriate type based on schema expectation
                # For simplicity here, we assume it can be directly assigned.
                # Pydantic validation later will catch type mismatches.
                config_data[normalized_key] = value
        return config_data

    def _load_and_validate_all_configs(self):
        """Loads, merges, and validates all configuration files."""
        merged_config_data: Dict[str, Any] = defaultdict(dict)

        for filename, schema in self._config_map.items():
            file_path = self._config_dir / filename
            file_data = self._load_json_file(file_path)
            
            # Use filename prefix (e.g., llm_models -> llm_models_config)
            # This allows schemas to be flat but config to be namespaced.
            namespace = filename.split('.')[0]
            if file_data:
                merged_config_data[namespace] = self._merge_configs(merged_config_data[namespace], file_data)
        
        # Apply environment variables to the top level merged data
        # Note: This is a simplistic approach; a robust solution might map env vars
        # to specific nested fields within their respective schemas.
        # For this example, we'll let Pydantic handle casting where possible.
        flat_env_overrides = {}
        for key, value in os.environ.items():
            # Example: OLLASH_LLM_MODELS_OLLAMA_URL -> llm_models.ollama_url
            if key.upper().startswith("OLLASH_"):
                # Split 'OLLASH_CONFIGNAME_FIELDNAME'
                parts = key.lower().replace("ollash_", "").split('_', 1)
                if len(parts) == 2:
                    config_name, field_name = parts
                    # Attempt to convert types for common cases
                    if value.lower() == 'true': value = True
                    elif value.lower() == 'false': value = False
                    elif value.isdigit(): value = int(value)
                    elif value.replace('.', '', 1).isdigit(): value = float(value)
                    
                    if config_name in merged_config_data:
                        merged_config_data[config_name][field_name] = value
                    else:
                        flat_env_overrides[field_name] = value # Could be top-level field in config schemas

        self._raw_config_data = merged_config_data

        # Validate against Pydantic schemas
        try:
            self._loaded_configs["llm_models"] = LLMModelsConfig.model_validate(merged_config_data.get("llm_models", {}))
            self._loaded_configs["agent_features"] = AgentFeaturesConfig.model_validate(merged_config_data.get("agent_features", {}))
            self._loaded_configs["tool_settings"] = ToolSettingsConfig.model_validate(merged_config_data.get("tool_settings", {}))
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
    This class follows the Singleton pattern to ensure only one instance
    manages global services like the logger and configuration loader.
    """
    _instance: Optional["AgentKernel"] = None
    _is_initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AgentKernel, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_dir: Union[str, Path] = "config", ollash_root_dir: Optional[Path] = None):
        if not self._is_initialized:
            self.ollash_root_dir = ollash_root_dir if ollash_root_dir else Path(os.getcwd())
            self._config_dir = Path(config_dir)

            # --- Initialize Configuration FIRST ---
            # Use a temporary standard logger for initial config loading errors, if any,
            # before the StructuredLogger is fully set up.
            temp_std_logger = logging.getLogger("TempAgentKernel")
            temp_std_logger.setLevel(logging.INFO)
            if not temp_std_logger.handlers:
                temp_std_logger.addHandler(logging.StreamHandler())
            temp_agent_logger = AgentLogger(structured_logger=StructuredLogger(log_file_path=self.ollash_root_dir / "logs" / "temp_kernel_init.log", logger_name="TempKernelInit"), logger_name="TempAgentKernelWrapper")
            
            # Instantiate ConfigLoader with the temporary logger
            self._config_loader = ConfigLoader(self._config_dir, temp_agent_logger)

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
            self._is_initialized = True

    def get_logger(self) -> AgentLogger:
        """Returns the global AgentLogger instance."""
        if not self._is_initialized:
            raise RuntimeError("AgentKernel must be initialized before accessing logger.")
        return self._agent_logger

    def get_llm_models_config(self) -> LLMModelsConfig:
        """Returns the validated LLM models configuration."""
        if not self._is_initialized:
            raise RuntimeError("AgentKernel must be initialized before accessing config.")
        config = self._config_loader.get_config("llm_models")
        if not config:
            raise RuntimeError("LLM models configuration not loaded.")
        return config # type: ignore

    def get_agent_features_config(self) -> AgentFeaturesConfig:
        """Returns the validated agent features configuration."""
        if not self._is_initialized:
            raise RuntimeError("AgentKernel must be initialized before accessing config.")
        config = self._config_loader.get_config("agent_features")
        if not config:
            raise RuntimeError("Agent features configuration not loaded.")
        return config # type: ignore

    def get_tool_settings_config(self) -> ToolSettingsConfig:
        """Returns the validated tool settings configuration."""
        if not self._is_initialized:
            raise RuntimeError("AgentKernel must be initialized before accessing config.")
        config = self._config_loader.get_config("tool_settings")
        if not config:
            raise RuntimeError("Tool settings configuration not loaded.")
        return config # type: ignore
    
    def get_full_config(self) -> Dict[str, Any]:
        """Returns the full raw, merged configuration as a dictionary."""
        if not self._is_initialized:
            raise RuntimeError("AgentKernel must be initialized before accessing full config.")
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