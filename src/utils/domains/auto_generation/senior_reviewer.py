import json
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

    JSON_RETRY_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.1,
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

        If the initial response is not valid JSON, retries once with a simplified
        prompt to avoid wasting a review attempt with no actionable issues.
        """
        project_summary = (
            f"Project Name: {project_name}\n\n"
            f"Description: {project_description}\n\n"
            f"README:\n{readme_content}\n\n"
            f"File Structure:\n{json.dumps(json_structure, indent=2)}\n\n"
            f"Files:\n" + "\n".join(current_files.keys())
        )
        system, user = AutoGenPrompts.senior_review_prompt(
            project_summary
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

        review_results = self.parser.extract_json(raw_review)

        if review_results is None:
            self.logger.warning(
                "Senior Reviewer returned non-JSON response. "
                "Retrying with simplified JSON-only prompt..."
            )
            review_results = self._retry_json_extraction(raw_review)

        if review_results is None:
            self.logger.error("Senior Reviewer could not produce valid JSON after retry. Assuming failed.")
            return {"status": "failed", "summary": "LLM returned invalid JSON review.", "issues": []}

        # Ensure 'status', 'summary', and 'issues' keys are present
        review_results.setdefault("status", "failed")
        review_results.setdefault("summary", "Review completed.")
        review_results.setdefault("issues", [])

        return review_results

    def _retry_json_extraction(self, raw_review: str) -> Dict | None:
        """Retry JSON extraction by asking the LLM to convert its own text review to JSON."""
        retry_system = (
            "You are a JSON formatter. Convert the following review text into "
            "a JSON object with exactly these keys: "
            "'status' (string: 'passed' or 'failed'), "
            "'summary' (string: one-sentence assessment), "
            "'issues' (list of objects with 'description', 'severity', 'recommendation', 'file'). "
            "Output ONLY valid JSON, nothing else."
        )
        retry_user = f"Convert this review to JSON:\n\n{raw_review[:4000]}"

        try:
            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": retry_system},
                    {"role": "user", "content": retry_user},
                ],
                tools=[],
                options_override=self.JSON_RETRY_OPTIONS,
            )
            raw_retry = response_data["message"]["content"]
            return self.parser.extract_json(raw_retry)
        except Exception as e:
            self.logger.error(f"JSON retry failed: {e}")
            return None
