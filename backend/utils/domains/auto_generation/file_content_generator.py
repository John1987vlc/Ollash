import json
from typing import Dict, List
from pathlib import Path # Added for Path.suffix
from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.documentation_manager import DocumentationManager # ADDED IMPORT
from backend.utils.core.fragment_cache import FragmentCache # CACHE SUPPORT
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
        documentation_manager: DocumentationManager, # ADDED PARAMETER
        fragment_cache: FragmentCache = None, # CACHE SUPPORT
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.documentation_manager = documentation_manager # STORE IT
        self.fragment_cache = fragment_cache # Optional cache
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

        # Query documentation for relevant context
        query_terms = [Path(file_path).name, Path(file_path).suffix]
        # json_structure might not always have "description" at the top level
        # if project description is available, use it
        if json_structure and "description" in json_structure:
            query_terms.append(json_structure["description"]) 
        elif "title" in json_structure: # Fallback to title
            query_terms.append(json_structure["title"])
        
        # Add terms from the readme that might be relevant
        readme_summary_len = min(500, len(readme_content))
        query_terms.append(readme_content[:readme_summary_len])


        documentation_context = ""
        # Create a more targeted query
        documentation_query = f"How to implement {file_path} for a project described as: {readme_content[:200]}..."

        retrieved_docs = self.documentation_manager.query_documentation(documentation_query, n_results=2) # Get top 2 results
        if retrieved_docs:
            documentation_context = "\n\nRelevant Documentation Snippets:\n" + "\n---\n".join([doc["document"] for doc in retrieved_docs])


        for attempt in range(max_retries):
            system_prompt, user_prompt = AutoGenPrompts.file_content_generation(
                file_path, readme_content, json_structure, related_files
            )
            # Append documentation context to the user prompt
            user_prompt += documentation_context

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