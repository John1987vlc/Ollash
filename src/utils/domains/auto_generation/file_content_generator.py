import json
from typing import Dict

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from .prompt_templates import AutoGenPrompts


class FileContentGenerator:
    """Phase 4: Generates initial content for each file."""

    DEFAULT_OPTIONS = {
        "num_ctx": 4096,
        "num_predict": 1024,
        "temperature": 0.6,
        "keep_alive": "0s",
    }

    # Extensions where output must be valid JSON
    JSON_EXTENSIONS = {".json"}

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

    def generate_file(
        self,
        file_path: str,
        readme_content: str,
        json_structure: dict,
        related_files: Dict[str, str],
        max_retries: int = 3,
    ) -> str:
        """Generate content for a single file.

        Uses the generic file_content_generation prompt for all file types.
        For JSON files, validates that the output is parseable JSON.

        Returns the generated content string, or empty string on failure.
        """
        is_json = any(file_path.endswith(ext) for ext in self.JSON_EXTENSIONS)
        content = ""

        for attempt in range(max_retries):
            system_prompt, user_prompt = AutoGenPrompts.file_content_generation(
                file_path, readme_content, json_structure, related_files
            )

            try:
                response_data, usage = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[],
                    options_override=self.options,
                )
                raw = response_data["message"]["content"]
                content = self.parser.extract_raw_content(raw)

                if is_json and content:
                    json.loads(content)  # Validate JSON
                    self.logger.info(
                        f"    Generated {len(content)} chars (attempt {attempt + 1}/{max_retries})"
                    )
                    break
                elif content:
                    self.logger.info(
                        f"    Generated {len(content)} chars (attempt {attempt + 1}/{max_retries})"
                    )
                    break
                else:
                    self.logger.warning(
                        f"    No content generated for {file_path} (attempt {attempt + 1}/{max_retries})"
                    )

            except json.JSONDecodeError as e:
                self.logger.error(
                    f"    Invalid JSON for {file_path} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                content = ""
            except Exception as e:
                self.logger.error(
                    f"    Error generating {file_path} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                content = ""

        if not content:
            self.logger.error(
                f"    Failed to generate valid content for {file_path} after {max_retries} attempts."
            )

        return content
