# src/core/config.py
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)


class Config:
    """
    A centralized configuration class to manage settings from .env files and environment variables.
    It loads simple key-value pairs and complex JSON strings from the environment.
    """

    def __init__(self):
        # Load environment variables from .env file located at the project root
        project_root = Path(__file__).parent.parent.parent
        dotenv_path = project_root / ".env"

        # Fallback for when .env is not found, useful for some execution contexts
        if not dotenv_path.exists():
            dotenv_path = project_root / ".env.example"
            if dotenv_path.exists():
                logger.info(f"Loading configuration from {dotenv_path}")
                load_dotenv(dotenv_path=dotenv_path, override=False)
        else:
            logger.info(f"Loading configuration from {dotenv_path}")
            load_dotenv(dotenv_path=dotenv_path, override=False)

        # --- Paths ---
        self.PROJECT_ROOT = project_root
        self.CONFIG_DIR = self.PROJECT_ROOT / "backend" / "config"

        # --- Load simple key-value settings ---
        self.OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "llama3:8b")
        self.DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", 300))
        self.DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", 0.5))
        self.BENCHMARK_ENABLED = os.getenv("BENCHMARK_ENABLED", "true").lower() == "true"

        # --- Load complex settings (JSON Files preferred, then ENV) ---
        self.AGENT_FEATURES = self._load_json("agent_features.json", "AGENT_FEATURES_JSON")
        self.ALERTS = self._load_json("alerts.json", "ALERTS_JSON")
        self.AUTO_BENCHMARK_TASKS = self._load_json("auto_benchmark_tasks.json", "AUTO_BENCHMARK_TASKS_JSON")
        self.AUTOMATION_TEMPLATES = self._load_json("automation_templates.json", "AUTOMATION_TEMPLATES_JSON")
        self.BENCHMARK_TASKS_EXTENDED = self._load_json(
            "benchmark_tasks_extended.json", "BENCHMARK_TASKS_EXTENDED_JSON"
        )
        self.BENCHMARK_TASKS = self._load_json("benchmark_tasks.json", "BENCHMARK_TASKS_JSON")
        self.LLM_MODELS = self._load_json("llm_models.json", "LLM_MODELS_JSON")
        self.TASKS = self._load_json("tasks.json", "TASKS_JSON")
        self.TOOL_SETTINGS = self._load_json("tool_settings.json", "TOOL_SETTINGS_JSON")

        # Legacy support: if individual settings from llm_models.json are in the old settings format, merge them
        if self.LLM_MODELS:
            self.OLLAMA_URL = self.LLM_MODELS.get("ollama_url", self.OLLAMA_URL)
            self.DEFAULT_MODEL = self.LLM_MODELS.get("default_model", self.DEFAULT_MODEL)
            self.DEFAULT_TIMEOUT = int(self.LLM_MODELS.get("default_timeout", self.DEFAULT_TIMEOUT))
            self.DEFAULT_TEMPERATURE = float(self.LLM_MODELS.get("default_temperature", self.DEFAULT_TEMPERATURE))

    def _load_json(self, file_name: str, env_var_name: str) -> dict | list | None:
        """
        Loads configuration from a JSON file if it exists, otherwise falls back to an environment variable.
        """
        file_path = self.CONFIG_DIR / file_name
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    logger.info(f"Loading configuration from file: {file_path}")
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading JSON from file '{file_path}': {e}")

        return self._load_json_from_env(env_var_name)

    def _load_json_from_env(self, env_var_name: str) -> dict | list | None:
        """
        Loads a JSON string from an environment variable and parses it.

        Args:
            env_var_name: The name of the environment variable.

        Returns:
            The parsed Python object (dict or list), or None if the variable is not set.
        """
        json_str = os.getenv(env_var_name)
        if not json_str:
            logger.warning(f"Environment variable '{env_var_name}' not found. Configuration may be incomplete.")
            return None
        try:
            # The JSON string might be wrapped in single quotes, which need to be removed.
            if json_str.startswith("'") and json_str.endswith("'"):
                json_str = json_str[1:-1]
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from environment variable '{env_var_name}': {e}")
            return None


_config_instance = None


def get_config(reload: bool = False) -> Config:
    """
    Returns the singleton Config instance.
    If reload is True, it forces a reload of the configuration from environment variables.
    """
    global _config_instance
    if _config_instance is None or reload:
        _config_instance = Config()
    return _config_instance


def reload_config() -> Config:
    """Convenience function for tests to force a reload of the config."""
    return get_config(reload=True)


# Create a default instance for the application to use
config = get_config()
