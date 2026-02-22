"""
Refactored RolePromptTemplates to use centralized YAML prompts.
Maintains the same interface while loading text from /prompts/roles/*.yaml.
"""

import logging
from typing import Optional
from backend.utils.core.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

class classproperty(object):
    """
    Decorator that converts a method with a single cls argument
    into a property that can be accessed directly from the class.
    """
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)

class RolePromptTemplates:
    """
    Prompt templates loaded from centralized YAML files.
    Optimized for different LLM roles.
    """

    _loader = PromptLoader()

    @staticmethod
    def get_system_prompt(role: str) -> str:
        """Get system prompt for a specific role from YAML files."""
        role_map = {
            "analyst": "roles/analyst.yaml",
            "writer": "roles/writer.yaml",
            "orchestration": "roles/orchestrator.yaml",
        }

        file_path = role_map.get(role)
        if not file_path:
            logger.warning(f"No prompt file found for role: {role}")
            return "You are a helpful AI assistant."

        content = RolePromptTemplates._loader.load_prompt(file_path)
        return content.get("system_prompt", "You are a helpful AI assistant.")

    @staticmethod
    def get_task_template(role: str, task_type: str, **kwargs) -> Optional[str]:
        """Get a task template for a role and task type from YAML files."""
        role_map = {
            "analyst": "roles/analyst.yaml",
            "writer": "roles/writer.yaml",
        }

        file_path = role_map.get(role)
        if not file_path:
            logger.warning(f"No task template file found for role: {role}")
            return None

        content = RolePromptTemplates._loader.load_prompt(file_path)
        tasks = content.get("tasks", {})
        template = tasks.get(task_type)

        if template and kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing key for prompt template {role}/{task_type}: {e}")
                return template

        return template

    # Backward compatibility: These were previously class attributes.
    @classproperty
    def ANALYST_SYSTEM_PROMPT(cls):
        return cls.get_system_prompt("analyst")

    @classproperty
    def WRITER_SYSTEM_PROMPT(cls):
        return cls.get_system_prompt("writer")

    @classproperty
    def ORCHESTRATOR_SYSTEM_PROMPT(cls):
        return cls.get_system_prompt("orchestration")

    @classproperty
    def ANALYST_TASK_TEMPLATES(cls):
        content = cls._loader.load_prompt("roles/analyst.yaml")
        return content.get("tasks", {})

    @classproperty
    def WRITER_TASK_TEMPLATES(cls):
        content = cls._loader.load_prompt("roles/writer.yaml")
        return content.get("tasks", {})
