from typing import Dict, List, Optional

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from .prompt_templates import AutoGenPrompts


class FileRefiner:
    """Phase 5: Refines and improves generated files."""

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
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
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
        if issues:
            system, user = AutoGenPrompts.file_refinement_with_issues(
                file_path, current_content, readme_excerpt, issues
            )
        else:
            system, user = AutoGenPrompts.file_refinement(
                file_path, current_content, readme_excerpt
            )

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

        # Sanity check: refined must be at least 50% of original length
        if refined and len(refined) > len(current_content) * 0.5:
            self.logger.info(f"    Refined ({len(refined)} chars)")
            return refined

        self.logger.warning(f"    Refinement produced poor result for {file_path}, keeping original")
        return None
