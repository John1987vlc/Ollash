from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.ollama_client import OllamaClient

from .prompt_templates import AutoGenPrompts


class ProjectPlanner:
    """Phase 1: Generates a README.md from a project description."""

    DEFAULT_OPTIONS = {
        "num_ctx": 4096,
        "num_predict": 2048,
        "temperature": 0.4,
        "keep_alive": "0s",
    }

    def __init__(self, llm_client: OllamaClient, logger: AgentLogger, options: dict = None):
        self.llm_client = llm_client
        self.logger = logger
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def generate_readme(
        self,
        project_name: str,
        project_description: str,
        features_and_stack: str = "",
        project_structure: str = ""
    ) -> str:
        """Generate a comprehensive README.md using specialized prompts."""
        system, user = AutoGenPrompts.readme_generation(
            project_name=project_name,
            project_description=project_description,
            features_and_stack=features_and_stack,
            project_structure=project_structure
        )
        response_data, usage = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        content = response_data["message"]["content"]
        self.logger.info(f"README generated: {len(content)} characters")
        return content
