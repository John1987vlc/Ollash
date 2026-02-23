"""
Contingency Planner for the Ollash Agent Framework.

This module provides a class to generate contingency plans when the
senior review phase of the AutoAgent fails.
"""

from typing import Any, Dict, List

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient


class ContingencyPlanner:
    """Generates contingency plans for AutoAgent."""

    def __init__(self, client: OllamaClient, logger: AgentLogger, parser: LLMResponseParser):
        """
        Initializes the ContingencyPlanner.

        Args:
            client: The Ollama client to use for generating the plan.
            logger: The logger instance.
            parser: The LLM response parser.
        """
        self.client = client
        self.logger = logger
        self.parser = parser

    def generate_contingency_plan(
        self, issues: List[Dict[str, Any]], project_description: str, readme: str
    ) -> Dict[str, Any]:
        """
        Generates a contingency plan to address senior reviewer issues using centralized prompts.

        Args:
            issues: A list of issues reported by the senior reviewer.
            project_description: The original project description.
            readme: The project's README file content.

        Returns:
            A dictionary representing the contingency plan.
        """
        self.logger.info("Generating contingency plan...")

        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader
            loader = PromptLoader()
            prompts = loader.load_prompt("domains/auto_generation/planning.yaml")

            system = prompts.get("contingency_planning", {}).get("system", "")
            user_template = prompts.get("contingency_planning", {}).get("user", "")

            issue_str = "\n".join([f"- {issue.get('description', 'N/A')}" for issue in issues])
            user = user_template.format(
                project_description=project_description,
                readme=readme,
                issues_str=issue_str
            )

            response, _ = self.client.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                tools=[]
            )
            content = response.get("message", {}).get("content", "")
            plan = self.parser.extract_json(content)
            self.logger.info("Contingency plan generated successfully.")
            return plan or {}
        except Exception as e:
            self.logger.error(f"Failed to generate contingency plan: {e}")
            return {}

    def _construct_prompt(self, *args, **kwargs):
        """Deprecated: Prompts are now in YAML."""
        pass
