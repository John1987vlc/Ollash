import json
from typing import Dict, List

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from .prompt_templates import AutoGenPrompts


class ProjectReviewer:
    """Phase 6: Final project review."""

    DEFAULT_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.5,
        "keep_alive": "0s",
    }

    def __init__(self, llm_client: OllamaClient, logger: AgentLogger, options: dict = None):
        self.llm_client = llm_client
        self.logger = logger
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def review(
        self,
        project_name: str,
        readme_excerpt: str,
        file_paths: List[str],
        validation_summary: Dict[str, int],
    ) -> str:
        """Generate a final project review. Returns the review text."""
        project_summary = f"Project: {project_name}\n\n"
        project_summary += f"README:\n{readme_excerpt}\n\n"
        project_summary += f"Files ({len(file_paths)}):\n"
        for p in file_paths[:20]:
            project_summary += f"- {p}\n"
        if len(file_paths) > 20:
            project_summary += f"... and {len(file_paths) - 20} more\n"
        project_summary += f"\nValidation Summary: {json.dumps(validation_summary)}"

        system, user = AutoGenPrompts.project_review(project_summary)
        response_data, usage = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        review = response_data["message"]["content"]
        self.logger.info("Final review completed")
        return review
