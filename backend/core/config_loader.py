"""
Configuration Loader for the Ollash Agent System.
"""
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

# Centralized config object and schemas
from backend.core.config import get_config
from backend.core.config_schemas import (AgentFeaturesConfig, LLMModelsConfig,
                                         ToolSettingsConfig)
from backend.utils.core.agent_logger import AgentLogger

T = TypeVar("T", bound=BaseModel)


class ConfigLoader:
    """
    Loads, merges, and validates configuration from the central config object.
    Stores validated configuration as Pydantic models.
    """

    def __init__(self, logger: AgentLogger):
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
        current_config = get_config()

        self._raw_config_data = {
            "llm_models": current_config.LLM_MODELS or {},
            "agent_features": current_config.AGENT_FEATURES or {},
            "tool_settings": current_config.TOOL_SETTINGS or {},
        }

        try:
            for key, model in self._config_map.items():
                self._loaded_configs[key] = model.model_validate(
                    self._raw_config_data.get(key, {})
                )
            self._logger.info("All configurations loaded and validated successfully.")
        except ValidationError as e:
            self._logger.error(f"Configuration validation failed: {e.errors()}")
            raise RuntimeError(f"Invalid configuration: {e}")
        except Exception as e:
            self._logger.error(
                f"An unexpected error occurred during config loading: {e}"
            )
            raise RuntimeError(f"Configuration error: {e}")

    def get_config(self, config_type: str) -> Optional[BaseModel]:
        """Returns a validated Pydantic config model by type."""
        return self._loaded_configs.get(config_type)

    def get_raw_config_data(self) -> Dict[str, Any]:
        """Returns the raw, merged config data."""
        return self._raw_config_data

    @property
    def logger(self) -> AgentLogger:
        return self._logger

    @logger.setter
    def logger(self, value: AgentLogger):
        self._logger = value
