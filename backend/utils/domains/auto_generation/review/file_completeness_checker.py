import asyncio
import json
from typing import Dict

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.analysis.file_validator import FileValidator, ValidationStatus
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient

from backend.utils.domains.auto_generation.utilities.prompt_templates import AutoGenPrompts


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
        max_retries_per_file: int = 3,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.validator = file_validator
        self.max_retries = max_retries_per_file
        self.options = options or self.DEFAULT_OPTIONS.copy()

    async def verify_and_fix(self, files: Dict[str, str], readme_context: str = "") -> Dict[str, str]:
        """Validate all files. For failures, attempt LLM-based fix up to max_retries times.
        Parallelizes fixing for multiple files.

        Args:
            files: {relative_path: content} dict
            readme_context: README excerpt for context in fix prompts

        Returns:
            Updated {relative_path: content} dict with fixes applied.
        """
        results = self.validator.validate_batch(files)
        fixed_files = dict(files)

        # Filter files that need attention
        to_fix = []
        for result in results:
            if result.status in (ValidationStatus.VALID, ValidationStatus.UNKNOWN_TYPE):
                self.logger.info(f"  VALID: {result.file_path} ({result.message})")
                continue
            to_fix.append(result)

        if not to_fix:
            return fixed_files

        async def fix_single_file(result_obj):
            file_path = result_obj.file_path
            is_empty = result_obj.status == ValidationStatus.EMPTY
            current_content = fixed_files.get(file_path, "")
            current_result = result_obj

            self.logger.warning(
                f"  {'EMPTY' if is_empty else 'FAILED'}: {file_path} - "
                f"{current_result.status.value}: {current_result.message}"
            )

            for attempt in range(1, self.max_retries + 1):
                self.logger.info(
                    f"    {'Generation' if is_empty else 'Fix'} attempt {attempt}/{self.max_retries} for {file_path}"
                )

                if is_empty:
                    system, user = await AutoGenPrompts.file_content_generation(
                        file_path, current_content, readme_context
                    )
                else:
                    system, user = await AutoGenPrompts.file_fix(
                        file_path, current_content, current_result.message, readme_context
                    )

                try:
                    # ACHTUNG: checking if achat exists or chat should be used.
                    # Based on project overview, most calls are Chat.
                    # MultiLanguageTestGenerator and others used .chat (sync).
                    # If llm_client is OllamaClient, .chat is sync.
                    # Some files use await self.llm_client.achat, but I should check if it exists.
                    if hasattr(self.llm_client, "achat"):
                        response_data, usage = await self.llm_client.achat(
                            messages=[
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                            tools=[],
                            options_override=self.options,
                        )
                    else:
                        response_data, usage = self.llm_client.chat(
                            messages=[
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                            tools=[],
                            options_override=self.options,
                        )
                    raw = response_data.get("message", {}).get("content", "") or response_data.get("content", "")

                    if file_path.lower().endswith(".json"):
                        # Use surgical JSON extraction for .json files
                        json_obj = self.parser.extract_json(raw)
                        if json_obj is not None:
                            new_content = json.dumps(json_obj, indent=2)
                        else:
                            new_content = self.parser.extract_raw_content(raw)
                    else:
                        new_content = self.parser.extract_raw_content(raw)

                    if not new_content.strip():
                        self.logger.warning(f"    Empty content returned on attempt {attempt} for {file_path}")
                        continue

                    new_result = self.validator.validate(file_path, new_content)

                    if new_result.status == ValidationStatus.VALID:
                        self.logger.info(
                            f"    {'GENERATED' if is_empty else 'FIXED'}: {file_path} on attempt {attempt}"
                        )
                        return file_path, new_content
                    else:
                        self.logger.warning(
                            f"    Still invalid after attempt {attempt} for {file_path}: {new_result.message}"
                        )
                        current_content = new_content
                        current_result = new_result
                        # If it's no longer empty, it's now a 'failed' file for the next attempt
                        is_empty = False

                except Exception as e:
                    self.logger.error(
                        f"    Error during {'generation' if is_empty else 'fix'} attempt {attempt} for {file_path}: {e}"
                    )

            self.logger.error(f"  GAVE UP: {file_path} after {self.max_retries} attempts")
            return file_path, current_content

        # Run all fixes in parallel
        tasks = [fix_single_file(r) for r in to_fix]
        updated_results = await asyncio.gather(*tasks)

        for path, content in updated_results:
            fixed_files[path] = content

        return fixed_files

    def get_validation_summary(self, files: Dict[str, str]) -> Dict[str, int]:
        """Returns a summary dict with counts by validation status."""
        results = self.validator.validate_batch(files)
        summary: Dict[str, int] = {}
        for r in results:
            key = r.status.value
            summary[key] = summary.get(key, 0) + 1
        return summary
