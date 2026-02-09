from typing import Dict

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from .prompt_templates import AutoGenPrompts


class SeniorReviewer:
    """Performs a comprehensive review of the generated project, acting as a senior architect."""

    DEFAULT_OPTIONS = {
        "num_ctx": 32768,
        "num_predict": 8192,
        "temperature": 0.2,
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

    def perform_review(
        self,
        project_description: str,
        project_name: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        review_attempt: int,
    ) -> Dict:
        """
        Performs a senior-level review of the entire project.
        Returns a dictionary with review status ('passed'/'failed'), summary, and issues.
        """
        system, user = AutoGenPrompts.senior_review_prompt(
            project_description, project_name, readme_content, json_structure, current_files, review_attempt
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        raw_review = response_data["message"]["content"]

        # The review should ideally be a structured JSON indicating pass/fail and issues
        review_results = self.parser.extract_json(raw_review)

        if review_results is None:
            self.logger.error("Senior Reviewer could not extract valid JSON from LLM response. Assuming failed.")
            return {"status": "failed", "summary": "LLM returned invalid JSON review.", "issues": []}

        # Ensure 'status', 'summary', and 'issues' keys are present
        review_results.setdefault("status", "failed")
        review_results.setdefault("summary", "Review completed.")
        review_results.setdefault("issues", [])

        return review_results
