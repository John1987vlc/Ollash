import json # Added import
from typing import Dict, Tuple

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
        max_retries: int = 3, # Added max_retries
    ) -> str:
        """Generate content for a single file.

        Returns the generated content string, or empty string on failure.
        """
        content = ""
        for attempt in range(max_retries):
            system_prompt = ""
            user_prompt = ""

            if file_path.endswith('package.json'):
                tech_stack_details = AutoGenPrompts._extract_tech_stack_details(readme_content)
                app_type = ""

                # Check for specific folder prefixes
                if file_path.startswith("frontend/"):
                    app_type = "frontend"
                elif file_path.startswith("backend/"):
                    app_type = "backend"

                if not app_type:
                    self.logger.error(f"Could not determine app type for package.json: {file_path}. Skipping generation.")
                    continue # Skip this file and try next if app_type cannot be determined

                system_prompt, user_prompt = AutoGenPrompts.package_json_generation(
                    file_path, tech_stack_details, app_type, json_structure, related_files
                )
            else:
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

                if file_path.endswith('package.json'):
                    if content:
                        # Attempt to parse as JSON for validation
                        json.loads(content)
                        self.logger.info(f"    Generated {len(content)} characters (package.json, attempt {attempt + 1}/{max_retries})")
                        break # Valid JSON, break retry loop
                    else:
                        self.logger.warning(f"    No content generated for {file_path} (package.json, attempt {attempt + 1}/{max_retries})")
                elif content:
                    self.logger.info(f"    Generated {len(content)} characters (attempt {attempt + 1}/{max_retries})")
                    break # Content generated, break retry loop
                else:
                    self.logger.warning(f"    No content generated for {file_path} (attempt {attempt + 1}/{max_retries})")

            except json.JSONDecodeError as e:
                self.logger.error(f"    Invalid JSON generated for {file_path} (attempt {attempt + 1}/{max_retries}): {e}")
                content = "" # Reset content as it's invalid
            except Exception as e:
                self.logger.error(f"    Error generating {file_path} (attempt {attempt + 1}/{max_retries}): {e}")
                content = ""

        if not content:
            self.logger.error(f"    Failed to generate valid content for {file_path} after {max_retries} attempts.")

        return content
