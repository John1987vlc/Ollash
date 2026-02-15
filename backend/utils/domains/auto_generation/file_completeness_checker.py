from typing import Dict

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.file_validator import FileValidator, ValidationStatus
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.ollama_client import OllamaClient

from .prompt_templates import AutoGenPrompts


class FileCompletenessChecker:
    """Verification loop: validates all generated files and fixes failures.

    Replaces the old END-OF-FILE marker approach with real syntax validation.
    For each file that fails validation, attempts to regenerate/fix via LLM
    up to max_retries times.
    """

    DEFAULT_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.2,
        "keep_alive": "0s",
    }

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        file_validator: FileValidator,
        max_retries_per_file: int = 2,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.validator = file_validator
        self.max_retries = max_retries_per_file
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def verify_and_fix(
        self, files: Dict[str, str], readme_context: str = ""
    ) -> Dict[str, str]:
        """Validate all files. For failures, attempt LLM-based fix up to max_retries times.

        Args:
            files: {relative_path: content} dict
            readme_context: README excerpt for context in fix prompts

        Returns:
            Updated {relative_path: content} dict with fixes applied.
        """
        results = self.validator.validate_batch(files)
        fixed_files = dict(files)

        for result in results:
            if result.status in (ValidationStatus.VALID, ValidationStatus.UNKNOWN_TYPE):
                self.logger.info(f"  VALID: {result.file_path} ({result.message})")
                continue

            if result.status == ValidationStatus.EMPTY:
                self.logger.warning(f"  EMPTY: {result.file_path} - skipping")
                continue

            # File needs fixing
            self.logger.warning(
                f"  FAILED: {result.file_path} - {result.status.value}: {result.message}"
            )
            current_content = fixed_files[result.file_path]

            for attempt in range(1, self.max_retries + 1):
                self.logger.info(
                    f"    Fix attempt {attempt}/{self.max_retries} for {result.file_path}"
                )

                system, user = AutoGenPrompts.file_fix(
                    result.file_path, current_content, result.message
                )

                try:
                    response_data, usage = self.llm_client.chat(
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        tools=[],
                        options_override=self.options,
                    )
                    raw = response_data["message"]["content"]
                    new_content = self.parser.extract_raw_content(raw)

                    new_result = self.validator.validate(result.file_path, new_content)

                    if new_result.status == ValidationStatus.VALID:
                        fixed_files[result.file_path] = new_content
                        self.logger.info(
                            f"    FIXED: {result.file_path} on attempt {attempt}"
                        )
                        break
                    else:
                        self.logger.warning(
                            f"    Still invalid after attempt {attempt}: {new_result.message}"
                        )
                        current_content = new_content

                except Exception as e:
                    self.logger.error(f"    Error during fix attempt {attempt}: {e}")
            else:
                self.logger.error(
                    f"  GAVE UP: {result.file_path} after {self.max_retries} attempts"
                )

        return fixed_files

    def get_validation_summary(self, files: Dict[str, str]) -> Dict[str, int]:
        """Returns a summary dict with counts by validation status."""
        results = self.validator.validate_batch(files)
        summary: Dict[str, int] = {}
        for r in results:
            key = r.status.value
            summary[key] = summary.get(key, 0) + 1
        return summary
