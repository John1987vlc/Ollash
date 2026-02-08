from typing import Dict, List, Tuple

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from .prompt_templates import AutoGenPrompts


class ImprovementSuggester:
    """Suggests improvements based on project context."""

    DEFAULT_OPTIONS = {
        "num_ctx": 4096,
        "num_predict": 1024,
        "temperature": 0.5,
    }

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def suggest_improvements(
        self,
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        loop_num: int,
    ) -> List[str]:
        """Suggests improvements for the project.

        Returns a list of suggested improvements.
        """
        system, user = AutoGenPrompts.suggest_improvements_prompt(
            project_description, readme_content, json_structure, current_files, loop_num
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        raw_suggestions = response_data["message"]["content"]
        # Assuming the LLM returns a markdown list or similar
        suggestions = [
            line.strip("- ").strip()
            for line in raw_suggestions.split("
")
            if line.strip().startswith("-")
        ]
        return suggestions
