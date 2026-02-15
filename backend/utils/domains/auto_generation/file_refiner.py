from pathlib import Path
from typing import Dict, List, Optional

from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.documentation_manager import DocumentationManager # ADDED IMPORT
from .prompt_templates import AutoGenPrompts


class FileRefiner:
    """Phase 5: Refines and improves generated files."""

    DEFAULT_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.2,
        "keep_alive": "0s",
    }

    # Files where drastic reduction is legitimate (e.g. cleaning hallucinated deps)
    REDUCTION_EXEMPT_FILES = {
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "package.json", "Gemfile", "Cargo.toml", "go.mod",
    }
    # Minimum ratio for normal files vs reduction-exempt files
    NORMAL_MIN_RATIO = 0.5
    EXEMPT_MIN_RATIO = 0.1

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        documentation_manager: DocumentationManager, # ADDED PARAMETER
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.documentation_manager = documentation_manager # STORE IT
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def refine_file(
        self,
        file_path: str,
        current_content: str,
        readme_excerpt: str,
        issues: Optional[List[Dict]] = None,
    ) -> Optional[str]:
        """Refine a single file. Returns refined content or None if refinement was worse.

        Args:
            file_path: Relative path of the file.
            current_content: Current file content.
            readme_excerpt: README excerpt for context.
            issues: Optional list of issue dicts from senior review, each with
                    'description', 'severity', 'recommendation', and optional 'file'.
        """

        # Query documentation for relevant context
        documentation_context = ""
        # Create a more targeted query based on the file and issues if any
        query_parts = [f"Refine {file_path}"]
        if issues:
            for issue in issues[:2]: # Take top 2 issues for query
                query_parts.append(issue.get("description", ""))
        query_parts.append(readme_excerpt[:100]) # Add a snippet of readme

        documentation_query = " ".join(query_parts)

        retrieved_docs = self.documentation_manager.query_documentation(documentation_query, n_results=2) # Get top 2 results
        if retrieved_docs:
            documentation_context = "\n\nRelevant Documentation Snippets:\n" + "\n---\n".join([doc["document"] for doc in retrieved_docs])


        if issues:
            system, user = AutoGenPrompts.file_refinement_with_issues(
                file_path, current_content, readme_excerpt, issues
            )
        else:
            system, user = AutoGenPrompts.file_refinement(
                file_path, current_content, readme_excerpt
            )

        # Append documentation context to the user prompt
        user += documentation_context

        response_data, usage = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        raw = response_data["message"]["content"]
        refined = self.parser.extract_raw_content(raw)

        # Sanity check: refined must meet minimum size ratio
        # Dependency files allow drastic reduction (cleaning hallucinated entries)
        filename = Path(file_path).name
        if filename in self.REDUCTION_EXEMPT_FILES:
            min_ratio = self.EXEMPT_MIN_RATIO
        else:
            min_ratio = self.NORMAL_MIN_RATIO

        if refined and len(refined) > len(current_content) * min_ratio:
            self.logger.info(f"    Refined ({len(refined)} chars)")
            return refined

        self.logger.warning(f"    Refinement produced poor result for {file_path}, keeping original")
        return None
