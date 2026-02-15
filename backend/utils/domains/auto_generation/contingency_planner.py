"""
Contingency Planner for the Ollash Agent Framework.

This module provides a class to generate contingency plans when the
senior review phase of the AutoAgent fails.
"""

from typing import Dict, List, Any

from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser

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

    def generate_contingency_plan(self, issues: List[Dict[str, Any]], project_description: str, readme: str) -> Dict[str, Any]:
        """
        Generates a contingency plan to address senior reviewer issues.

        Args:
            issues: A list of issues reported by the senior reviewer.
            project_description: The original project description.
            readme: The project's README file content.

        Returns:
            A dictionary representing the contingency plan.
        """
        self.logger.info("Generating contingency plan...")

        prompt = self._construct_prompt(issues, project_description, readme)

        try:
            response, _ = self.client.chat(prompt, tools=[])
            content = response.get("message", {}).get("content", "")
            plan = self.parser.extract_json(content)
            self.logger.info("Contingency plan generated successfully.")
            return plan or {}
        except Exception as e:
            self.logger.error(f"Failed to generate contingency plan: {e}")
            return {}

    def _construct_prompt(self, issues: List[Dict[str, Any]], project_description: str, readme: str) -> List[Dict[str, str]]:
        """Constructs the prompt for the contingency planner."""

        issue_str = "\n".join([f"- {issue.get('description', 'N/A')}" for issue in issues])

        prompt = f"""
        The senior review for the project has failed. Here are the issues that were found:
        {issue_str}

        Here is the original project description:
        {project_description}

        And here is the project's README:
        {readme}

        Please generate a new plan to address these issues. The plan should be in JSON format and should include a list of actions to take.
        Each action should have a 'type' (e.g., 'refine_file', 'add_file', 'delete_file') and a 'file_path' if applicable.
        """

        return [
            {"role": "system", "content": "You are a contingency planner for an AI agent."},
            {"role": "user", "content": prompt}
        ]
