from typing import Dict, List

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.ollama_client import OllamaClient

from .prompt_templates import AutoGenPrompts


class ImprovementPlanner:
    """Generates a plan to implement suggested improvements."""

    DEFAULT_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.3,
        "keep_alive": "0s",
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

    def generate_plan(
        self,
        suggestions: List[str],
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
    ) -> Dict:
        """Generates a detailed plan to implement suggested improvements.

        Returns a dictionary representing the plan.
        """
        system, user = AutoGenPrompts.generate_improvement_plan_prompt(
            suggestions,
            project_description,
            readme_content,
            json_structure,
            current_files,
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        raw_plan = response_data["message"]["content"]
        plan = self.parser.extract_json(raw_plan)
        if plan is None:
            self.logger.error("Could not extract valid JSON plan from LLM response.")
            return {}
        return plan
