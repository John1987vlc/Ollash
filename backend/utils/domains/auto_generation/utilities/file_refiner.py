from pathlib import Path
from typing import Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.io.documentation_manager import DocumentationManager
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient

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
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "package.json",
        "Gemfile",
        "Cargo.toml",
        "go.mod",
    }
    # Minimum ratio for normal files vs reduction-exempt files
    NORMAL_MIN_RATIO = 0.5
    EXEMPT_MIN_RATIO = 0.1

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        documentation_manager: DocumentationManager,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.documentation_manager = documentation_manager
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def simplify_file_content(self, file_path: str, content: str, remove_redundancy: bool = True) -> Optional[str]:
        """
        Aggressively simplifies a file to resolve persistent logic errors or
        architectural complexity issues.
        """
        self.logger.info(f"  Aggressively simplifying {file_path}...")

        # We use a specialized prompt for simplification
        system = "You are a Senior Architect focused on KISS (Keep It Simple, Stupid). Your goal is to simplify code, remove redundancy, and ensure it is 100% functional and error-free."
        user = f"""## TASK: Simplify the following file to improve stability and resolve issues.
FILE: {file_path}

## CONSTRAINTS:
1. Remove any redundant or overly complex logic.
2. Ensure the code remains functional and meets the core requirements.
3. Output ONLY the simplified source code inside a Markdown block.
4. NO conversational text.

## CURRENT CONTENT:
```
{content}
```
"""
        try:
            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[],
                options_override=self.options,
            )
            raw = response_data["message"]["content"]
            simplified = self.parser.extract_raw_content(raw)

            if simplified and len(simplified) > 20:
                self.logger.info(f"    Successfully simplified {file_path}")
                return simplified
        except Exception as e:
            self.logger.error(f"  Error simplifying {file_path}: {e}")

        return None

    def refine_file(
        self,
        file_path: str,
        current_content: str,
        readme_excerpt: str,
        issues: Optional[list] = None,
    ) -> Optional[str]:
        """Refine a single file. Returns refined content or None if refinement was worse.

        Args:
            file_path: Relative path of the file.
            current_content: Current file content.
            readme_excerpt: README excerpt for context.
            issues: Optional list of issue dicts from senior review.
        """

        # Query documentation for relevant context
        documentation_context = ""
        query_parts = [f"Refine {file_path}"]
        if issues:
            for issue in issues[:2]:  # Take top 2 issues for query
                query_parts.append(issue.get("description", ""))
        query_parts.append(readme_excerpt[:100])

        documentation_query = " ".join(query_parts)

        retrieved_docs = self.documentation_manager.query_documentation(documentation_query, n_results=2)
        if retrieved_docs:
            documentation_context = "\n\nRelevant Documentation Snippets:\n" + "\n---\n".join(
                [doc["document"] for doc in retrieved_docs]
            )

        # Prepare the combined context (README + documentation)
        combined_context = f"PROJECT CONTEXT (README):\n{readme_excerpt}\n"
        if documentation_context:
            combined_context += documentation_context

        # NEW: Specialized Doc Refinement Path
        is_doc = file_path.lower().endswith((".md", ".txt", ".rst"))

        if is_doc:
            system, user = AutoGenPrompts.documentation_refinement(
                file_path, current_content, project_description=combined_context
            )
        elif issues:
            # Se formatea la cadena de issues para que coincida con el método esperado
            issues_str = "\n".join([f"- {i.get('description')}" for i in issues])
            system, user = AutoGenPrompts.file_refinement_with_issues(
                file_path, current_content, issues_str, context=combined_context
            )
        else:
            # file_refinement en prompt_templates.py ahora acepta context
            system, user = AutoGenPrompts.file_refinement(file_path, current_content, context=combined_context)

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
            refined = self.parser.extract_raw_content(raw)

            # 3. Anti-Hallucination Guard
            hallucination_indicators = [
                "example_function",
                "SELECT * FROM table_name",
                "Your JSON is properly formatted",
                "proper Python syntax",
                "Certainly! Here's how",
                "Hope this helps",
            ]
            if refined and any(ind.lower() in refined.lower() for ind in hallucination_indicators):
                self.logger.warning(
                    f"  [HALLUCINATION DETECTED] Refinement of {file_path} contained generic example code."
                )
                return None

            # Sanity check
            filename = Path(file_path).name
            min_ratio = self.EXEMPT_MIN_RATIO if filename in self.REDUCTION_EXEMPT_FILES else self.NORMAL_MIN_RATIO

            if refined and len(refined) > len(current_content) * min_ratio:
                # For documentation, ensure it didn't just replace content with total garbage
                if filename.lower().endswith((".md", ".txt")) and "README" in filename.upper():
                    # Check if at least some keyword from the original or project exists
                    if len(refined) < 50:
                        return None  # Too short for a real README

                self.logger.info(f"    Refined {file_path} ({len(refined)} chars)")
                return refined

        except Exception as e:
            self.logger.error(f" Error during refinement of {file_path}: {e}")

        self.logger.warning(f" Refinement produced poor result or failed for {file_path}, keeping original")
        return None
