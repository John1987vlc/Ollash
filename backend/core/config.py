import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load(filename: str) -> dict:
    path = _CONFIG_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not load %s: %s", filename, e)
        return {}


class Config:
    """Unified configuration loaded from backend/config/*.json and .env."""

    def __init__(self):
        root = Path(__file__).parent.parent.parent
        dotenv_path = root / ".env"
        if not dotenv_path.exists():
            dotenv_path = root / ".env.example"
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=False)

        self.PROJECT_ROOT = root
        self.CONFIG_DIR = _CONFIG_DIR

        # --- Load all config files ---
        ollama = _load("ollama.json")
        models = _load("models.json")
        agent_roles = _load("agent_roles.json")
        tools = _load("tools.json")
        runtime = _load("runtime.json")
        features = _load("features.json")
        optimizations = _load("optimizations.json")
        phase_features = _load("phase_features.json")
        alert_thresholds = _load("alert_thresholds.json")
        automation_templates = _load("automation_templates.json")
        auto_benchmark_tasks = _load("auto_benchmark_tasks.json")
        auto_benchmark_tasks_phases = _load("auto_benchmark_tasks_phases.json")
        security_policies = _load("security_policies.json")

        # --- Top-level convenience attributes (env vars take precedence) ---
        self.OLLAMA_URL: str = os.getenv("OLLAMA_URL", ollama.get("url", "http://127.0.0.1:11434"))
        self.DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", ollama.get("default_model", "qwen3.5:4b"))
        self.DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", ollama.get("timeout", 600)))
        self.DEFAULT_TEMPERATURE: float = float(os.getenv("DEFAULT_TEMPERATURE", ollama.get("temperature", 0.4)))
        self.DEFAULT_NUM_CTX: int = int(os.getenv("DEFAULT_NUM_CTX", ollama.get("num_ctx", 16384)))
        self.DEFAULT_REPEAT_PENALTY: float = float(os.getenv("DEFAULT_REPEAT_PENALTY", ollama.get("repeat_penalty", 1.15)))
        self.BENCHMARK_ENABLED: bool = os.getenv("BENCHMARK_ENABLED", "true").lower() == "true"

        # --- Backward-compat dicts (used by existing consumers) ---
        self.LLM_MODELS: dict = {
            "ollama_url": self.OLLAMA_URL,
            "default_model": self.DEFAULT_MODEL,
            "default_timeout": self.DEFAULT_TIMEOUT,
            "default_temperature": self.DEFAULT_TEMPERATURE,
            "agent_roles": agent_roles,
            **models,
        }
        self.TOOL_SETTINGS: dict = {**tools, **runtime}
        self.AGENT_FEATURES: dict = {
            **features,
            "small_model_optimizations": optimizations.get("small_model", {}),
            "mid_model_optimizations": optimizations.get("mid_model", {}),
            **phase_features,
        }
        self.ALERTS: dict = alert_thresholds
        self.AUTOMATION_TEMPLATES: dict = automation_templates
        self.AUTO_BENCHMARK_TASKS: dict = auto_benchmark_tasks
        self.AUTO_BENCHMARK_TASKS_PHASES: dict = auto_benchmark_tasks_phases
        self.SECURITY_POLICIES: dict = security_policies

        # --- Structured access (new preferred API) ---
        self.OLLAMA: dict = {**ollama, "url": self.OLLAMA_URL}
        self.MODELS: dict = models
        self.AGENT_ROLES: dict = agent_roles
        self.TOOLS: dict = tools
        self.RUNTIME: dict = runtime
        self.FEATURES: dict = features
        self.OPTIMIZATIONS: dict = optimizations
        self.PHASE_FEATURES: dict = phase_features

    def get(self, key: str, default=None):
        """Dict-style access for legacy callers using config.get('key')."""
        return getattr(self, key.upper(), default)


_config_instance: Config | None = None


def get_config(reload: bool = False) -> Config:
    global _config_instance
    if _config_instance is None or reload:
        _config_instance = Config()
    return _config_instance


def reload_config() -> Config:
    return get_config(reload=True)


config = get_config()
