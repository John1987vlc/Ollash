"""
Refactored RolePromptTemplates to use centralized YAML prompts.
Maintains the same interface while loading text from /prompts/roles/*.yaml.
"""

import logging
from typing import Optional
from backend.utils.core.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class RolePromptTemplates:
    """
    Prompt templates loaded from centralized YAML files.
    Optimized for different LLM roles.
    """

    _loader = PromptLoader()

    @staticmethod
    async def get_system_prompt(role: str) -> str:
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

        content = await RolePromptTemplates._loader.load_prompt(file_path)
        return content.get("system_prompt", "You are a helpful AI assistant.")

    @staticmethod
    def get_system_prompt_sync(role: str) -> str:
        """Synchronous version of get_system_prompt."""
        role_map = {
            "analyst": "roles/analyst.yaml",
            "writer": "roles/writer.yaml",
            "orchestration": "roles/orchestrator.yaml",
        }

        file_path = role_map.get(role)
        if not file_path:
            return "You are a helpful AI assistant."

        content = RolePromptTemplates._loader.load_prompt_sync(file_path)
        return content.get("system_prompt", "You are a helpful AI assistant.")

    @staticmethod
    async def get_task_template(role: str, task_type: str, **kwargs) -> Optional[str]:
        """Get a task template for a role and task type from YAML files."""
        role_map = {
            "analyst": "roles/analyst.yaml",
            "writer": "roles/writer.yaml",
        }

        file_path = role_map.get(role)
        if not file_path:
            logger.warning(f"No task template file found for role: {role}")
            return None

        content = await RolePromptTemplates._loader.load_prompt(file_path)
        tasks = content.get("tasks", {})
        template = tasks.get(task_type)

        if template and kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing key for prompt template {role}/{task_type}: {e}")
                return template

        return template

    @staticmethod
    def get_task_template_sync(role: str, task_type: str, **kwargs) -> Optional[str]:
        """Synchronous version of get_task_template."""
        role_map = {
            "analyst": "roles/analyst.yaml",
            "writer": "roles/writer.yaml",
        }

        file_path = role_map.get(role)
        if not file_path:
            return None

        content = RolePromptTemplates._loader.load_prompt_sync(file_path)
        tasks = content.get("tasks", {})
        template = tasks.get(task_type)

        if template and kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                return template

        return template

    @classmethod
    async def get_analyst_task_templates(cls):
        content = await cls._loader.load_prompt("roles/analyst.yaml")
        return content.get("tasks", {})

    @classmethod
    def get_analyst_task_templates_sync(cls):
        content = cls._loader.load_prompt_sync("roles/analyst.yaml")
        return content.get("tasks", {})

    @classmethod
    async def get_writer_task_templates(cls):
        content = await cls._loader.load_prompt("roles/writer.yaml")
        return content.get("tasks", {})

    @classmethod
    def get_writer_task_templates_sync(cls):
        content = cls._loader.load_prompt_sync("roles/writer.yaml")
        return content.get("tasks", {})


# Backwards-compatible class attributes populated at import time
try:
    RolePromptTemplates.ANALYST_SYSTEM_PROMPT = RolePromptTemplates.get_system_prompt_sync("analyst")
    RolePromptTemplates.WRITER_SYSTEM_PROMPT = RolePromptTemplates.get_system_prompt_sync("writer")
    RolePromptTemplates.ORCHESTRATOR_SYSTEM_PROMPT = RolePromptTemplates.get_system_prompt_sync("orchestration")
    RolePromptTemplates.ANALYST_TASK_TEMPLATES = RolePromptTemplates.get_analyst_task_templates_sync()
    RolePromptTemplates.WRITER_TASK_TEMPLATES = RolePromptTemplates.get_writer_task_templates_sync()
except Exception:
    RolePromptTemplates.ANALYST_SYSTEM_PROMPT = "You are a helpful analyst AI assistant."
    RolePromptTemplates.WRITER_SYSTEM_PROMPT = "You are a helpful writer AI assistant."
    RolePromptTemplates.ORCHESTRATOR_SYSTEM_PROMPT = "You are a helpful orchestration AI assistant."
    RolePromptTemplates.ANALYST_TASK_TEMPLATES = {}
    RolePromptTemplates.WRITER_TASK_TEMPLATES = {}
