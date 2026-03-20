import json
from typing import Dict, Optional

from pydantic import ValidationError

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.system.retry_policy import RetryPolicy

from backend.utils.domains.auto_generation.utilities.prompt_templates import AutoGenPrompts
from backend.core.config_schemas import SeniorReviewOutput


class SeniorReviewer:
    """Performs a comprehensive review of the generated project, acting as a senior architect."""

    DEFAULT_OPTIONS = {
        "num_ctx": 32768,
        "num_predict": 8192,
        "temperature": 0.2,
        "keep_alive": "0s",
    }

    # I10: wider context for 30B+ models — matches _CHAR_BUDGET_LARGE (60K chars ≈ 64K tokens)
    LARGE_MODEL_OPTIONS = {
        "num_ctx": 65536,
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
        # I10: auto-select wider context for 30B+ models when no explicit options provided
        if options is None:
            import re as _re

            model_name_raw = getattr(llm_client, "model", "")
            model_name = model_name_raw if isinstance(model_name_raw, str) else ""
            m = _re.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
            model_size = float(m.group(1)) if m else 0.0
            options = self.LARGE_MODEL_OPTIONS.copy() if model_size >= 30.0 else self.DEFAULT_OPTIONS.copy()
        self.options = options
        self.retry_policy = RetryPolicy(max_attempts=2)

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
        Ensures structural integrity using Pydantic validation.
        """
        project_summary = (
            f"Project Name: {project_name}\n\n"
            f"Description: {project_description}\n\n"
            f"README:\n{readme_content}\n\n"
            f"File Structure:\n{json.dumps(json_structure, indent=2)}\n\n"
            f"Files:\n" + "\n".join(current_files.keys())
        )
        system, user = AutoGenPrompts.senior_review_prompt(project_summary)

        last_error = ""
        for attempt in range(1, 3):
            try:
                current_user = user
                if last_error:
                    current_user += f"\n\nCRITICAL: Previous output failed validation:\n{last_error}\n\nPlease fix the JSON and ensure all fields ('status', 'summary', 'issues') are correct."

                response_data, _ = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": current_user},
                    ],
                    tools=[],
                    options_override=self.options,
                )

                raw_review = response_data.get("content", "") or response_data.get("message", {}).get("content", "")
                parsed_json = self.parser.extract_json(raw_review)

                if parsed_json is None:
                    # Retry once with simplified extractor if parsing failed completely
                    parsed_json = self._retry_json_extraction(raw_review)

                if parsed_json:
                    # Pydantic Hardening
                    validated = SeniorReviewOutput.model_validate(parsed_json)
                    return validated.model_dump()

                raise ValueError("Could not extract valid JSON from review.")

            except (ValidationError, ValueError, Exception) as e:
                last_error = str(e)
                self.logger.warning(f"  ⚠ Senior Review attempt {attempt} failed validation: {last_error}")

        self.logger.error("Senior Reviewer could not produce validated JSON. Using emergency fail status.")
        return {
            "status": "failed",
            "summary": f"Senior Review failed to produce validated output: {last_error}",
            "issues": [],
        }

    def _retry_json_extraction(self, raw_review: str) -> Optional[Dict]:
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
            raw_retry = response_data.get("content", "") or response_data.get("message", {}).get("content", "")
            return self.parser.extract_json(raw_retry)
        except Exception as e:
            self.logger.error(f"JSON retry failed: {e}")
            return None
