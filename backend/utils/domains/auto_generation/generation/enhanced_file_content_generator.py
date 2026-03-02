"""Enhanced File Content Generator that uses logic plans for better implementation."""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.system.retry_policy import RetryPolicy


class EnhancedFileContentGenerator:
    """
    Improved file content generator that:
    1. Uses detailed implementation plans from LogicPlanningPhase
    2. Validates content incrementally
    3. Handles partial/incomplete file generation with retry
    4. Breaks large functions into smaller chunks
    5. Optionally queries DocumentationManager (RAG) for relevant examples
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser = None,
        documentation_manager=None,
        code_patcher=None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.response_parser = response_parser or LLMResponseParser()
        self.documentation_manager = documentation_manager
        self.max_retries = 3
        self.retry_policy = RetryPolicy(max_attempts=self.max_retries)
        # Lazy import to avoid circular dependency; CodePatcher lives in the same package
        if code_patcher is not None:
            self._code_patcher = code_patcher
        else:
            from backend.utils.domains.auto_generation.code_patcher import CodePatcher

            self._code_patcher = CodePatcher(llm_client, logger, self.response_parser)

    def generate_file_with_plan(
        self,
        file_path: str,
        logic_plan: Dict[str, Any],
        project_description: str,
        readme: str,
        structure: Dict[str, Any],
        related_files: Dict[str, str],
    ) -> str:
        """
        Generate file content using a detailed implementation plan.

        Args:
            file_path: Path to file being generated
            logic_plan: Detailed plan from LogicPlanningPhase
            project_description: Original project description
            readme: Project README content
            structure: Project structure
            related_files: Related files for context

        Returns:
            Generated file content
        """

        self.logger.info(f"Generating {file_path} with detailed plan...")

        # Extract plan details
        purpose = logic_plan.get("purpose", "")
        exports = logic_plan.get("exports", [])
        imports = logic_plan.get("imports", [])
        main_logic = logic_plan.get("main_logic", [])
        validation = logic_plan.get("validation", [])
        dependencies = logic_plan.get("dependencies", [])

        # Build context for generation
        context = self._build_detailed_context(
            file_path,
            purpose,
            exports,
            imports,
            main_logic,
            validation,
            dependencies,
            related_files,
            readme,
            structure,
        )

        # Generate with retry logic
        for attempt in range(self.max_retries):
            try:
                content = self._generate_with_prompt(file_path, context, purpose, exports, main_logic, validation)

                if self._validate_content(content, file_path, exports, validation):
                    return content

                self.logger.warning(f"  Attempt {attempt + 1}: Generated content failed validation for {file_path}")

            except Exception as e:
                self.logger.error(f"  Attempt {attempt + 1} failed for {file_path}: {e}")

        # If all retries failed, return partial content with comments
        self.logger.error(f"Failed to generate valid {file_path} after {self.max_retries} attempts")
        return self._generate_fallback_skeleton(file_path, purpose, exports, imports)

    async def generate_file_with_plan_streaming(
        self,
        file_path: str,
        logic_plan: Dict[str, Any],
        project_description: str,
        readme: str,
        structure: Dict[str, Any],
        related_files: Dict[str, str],
        chunk_callback: Optional[Callable] = None,
    ) -> str:
        """Async streaming variant of ``generate_file_with_plan``.

        Calls *chunk_callback* (sync or async) for each token chunk produced by
        the LLM, enabling live streaming to the Blackboard / SSE frontend.
        Falls back to the synchronous path on any error.

        Args:
            chunk_callback: Called with each streamed token chunk (str).
                            May be an async coroutine function.

        Returns:
            Full generated file content (post-processed, same as sync version).
        """
        purpose = logic_plan.get("purpose", "")
        exports = logic_plan.get("exports", [])
        imports = logic_plan.get("imports", [])
        main_logic = logic_plan.get("main_logic", [])
        validation = logic_plan.get("validation", [])
        dependencies = logic_plan.get("dependencies", [])

        context = self._build_detailed_context(
            file_path,
            purpose,
            exports,
            imports,
            main_logic,
            validation,
            dependencies,
            related_files,
            readme,
            structure,
        )

        file_ext = Path(file_path).suffix
        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = loader.load_prompt("domains/auto_generation/code_gen.yaml")
            lang_rules_map = prompts.get("language_rules", {})
            lang_rule = lang_rules_map.get(file_ext, lang_rules_map.get("default", ""))
            system_template = prompts.get("file_gen_v2", {}).get("system", "")
            user_template = prompts.get("file_gen_v2", {}).get("user", "")
            if not system_template or not user_template:
                raise ValueError("Prompt templates not found")
            system = system_template.format(language_specific_rules=lang_rule)
            user = user_template.format(file_path=file_path, context=context, exports=", ".join(exports))
        except Exception as exc:
            self.logger.warning(f"[streaming] Prompt load failed for '{file_path}': {exc}; using sync fallback")
            return self.generate_file_with_plan(
                file_path=file_path,
                logic_plan=logic_plan,
                project_description=project_description,
                readme=readme,
                structure=structure,
                related_files=related_files,
            )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            result, _ = await self.llm_client.stream_chat(
                messages=messages,
                chunk_callback=chunk_callback,
                options_override={"temperature": 0.2},
            )
            content = result.get("content", "")
            return self.response_parser.extract_code_block(content) or content
        except Exception as exc:
            self.logger.warning(f"[streaming] stream_chat failed for '{file_path}': {exc}; using sync fallback")
            return self.generate_file_with_plan(
                file_path=file_path,
                logic_plan=logic_plan,
                project_description=project_description,
                readme=readme,
                structure=structure,
                related_files=related_files,
            )

    def _build_detailed_context(
        self,
        file_path: str,
        purpose: str,
        exports: List[str],
        imports: List[str],
        main_logic: List[str],
        validation: List[str],
        dependencies: List[str],
        related_files: Dict[str, str],
        readme: str,
        structure: Dict[str, Any],
    ) -> str:
        """Build detailed context for file generation, including optional RAG snippets."""

        context = f"""
## File: {file_path}
Purpose: {purpose}

### Requirements
Exports: {", ".join(exports)}
Imports: {", ".join(imports) if imports else "Standard only"}
Logic:
{chr(10).join(f"- {logic}" for logic in main_logic)}

### Context
Structure: {list(structure.keys()) if isinstance(structure, dict) else "Provided"}
Related files: {", ".join(related_files.keys()) if related_files else "None"}

### Validation
{chr(10).join(f"- {v}" for v in validation)}
"""
        # Append RAG documentation snippets when available
        doc_snippets = self._get_documentation_snippets(file_path, purpose)
        if doc_snippets:
            context += doc_snippets

        return context

    def _get_documentation_snippets(self, file_path: str, purpose: str) -> str:
        """Query documentation manager for relevant code examples (RAG)."""
        if not self.documentation_manager:
            return ""
        try:
            query = f"How to implement {file_path}: {purpose[:200]}"
            docs = self.documentation_manager.query_documentation(query, n_results=2)
            if docs:
                snippets = "\n---\n".join(d["document"] for d in docs)
                return f"\n\n### Relevant Documentation:\n{snippets}"
        except Exception as e:
            self.logger.warning(f"RAG lookup failed: {e}")
        return ""

    def _generate_with_prompt(
        self,
        file_path: str,
        context: str,
        purpose: str,
        exports: List[str],
        main_logic: List[str],
        validation: List[str],
    ) -> str:
        """Generate file content with specialized prompt from YAML."""

        file_ext = Path(file_path).suffix

        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = loader.load_prompt("domains/auto_generation/code_gen.yaml")

            if not prompts:
                return self._generate_fallback_skeleton(file_path, purpose, exports, [])

            lang_rules_map = prompts.get("language_rules", {})
            lang_rule = lang_rules_map.get(file_ext, lang_rules_map.get("default", ""))

            system_template = prompts.get("file_gen_v2", {}).get("system", "")
            if not system_template:
                return self._generate_fallback_skeleton(file_path, purpose, exports, [])

            system = system_template.format(language_specific_rules=lang_rule)

            user_template = prompts.get("file_gen_v2", {}).get("user", "")
            if not user_template:
                return self._generate_fallback_skeleton(file_path, purpose, exports, [])

            user = user_template.format(file_path=file_path, context=context, exports=", ".join(exports))

            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[],
                options_override={"temperature": 0.2},
            )

            content = response_data["message"]["content"]
            return self.response_parser.extract_code_block(content) or content

        except Exception as e:
            self.logger.error(f"Failed to load centralized generation prompt: {e}")
            # Minimal fallback
            return self._generate_fallback_skeleton(file_path, purpose, exports, [])

    def _get_code_generation_system_prompt(self, file_ext: str) -> str:
        """Deprecated: Prompts are now loaded from YAML in _generate_with_prompt."""
        return "You are an expert developer. Return ONLY the code."

    def _validate_content(self, content: str, file_path: str, exports: List[str], validation: List[str]) -> bool:
        """Validate that generated content meets requirements."""

        if not content or len(content.strip()) < 20:
            self.logger.warning(f"  Content too short for {file_path}")
            return False

        file_ext = Path(file_path).suffix

        # Check for required exports with word boundaries to avoid false positives
        for export in exports:
            clean_export = export.replace("()", "").strip()
            if not re.search(r"\b" + re.escape(clean_export) + r"\b", content):
                self.logger.warning(f"  Missing export '{clean_export}' in {file_path}")
                return False

        # Check that code doesn't have obvious placeholder markers
        placeholders = ["TODO", "FIXME", "XXX", "implementation goes here", "add your logic"]
        for p in placeholders:
            if p.lower() in content.lower():
                self.logger.warning(f"  Placeholder found: '{p}' in {file_path}")
                return False

        # Language-specific validation
        if file_ext == ".py":
            # Check for unmatched brackets
            if content.count("(") != content.count(")"):
                self.logger.warning(f"  Unmatched parentheses in {file_path}")
                return False
            # Detect skeletons: many 'pass' or '...' and very short
            skeleton_count = content.count("pass") + content.count("...")
            if skeleton_count > len(exports) and len(content.strip().split("\n")) < 10:
                self.logger.warning(f"  Skeleton detected for {file_path}")
                return False

        return True

    def _generate_fallback_skeleton(self, file_path: str, purpose: str, exports: List[str], imports: List[str]) -> str:
        """Generate a basic skeleton when full generation fails."""

        file_ext = Path(file_path).suffix

        if file_ext == ".py":
            imports_str = "\n".join("from ... import ..." for _ in imports) if imports else ""
            exports_parts = []
            for e in exports:
                if "()" in e:
                    func_name = e.replace("()", "")
                    exports_parts.append(f'def {func_name}():\n    """Implement {e}."""\n    pass')
                else:
                    exports_parts.append(f'class {e}:\n    """Implement {e}."""\n    pass')
            exports_str = "\n\n".join(exports_parts)
            skeleton = f'''"""
{purpose}
"""
{imports_str}

{exports_str}
'''
        elif file_ext == ".js" or file_ext == ".ts":
            imports_str = "\n".join('import { ... } from "...";' for _ in imports) if imports else ""
            exports_parts = []
            for e in exports:
                if "()" in e:
                    exports_parts.append(f"function {e} {{\n  // TODO: Implement\n}}\n")
                else:
                    exports_parts.append(f"class {e} {{\n  // TODO: Implement\n}}\n")
            exports_str = "\n".join(exports_parts)
            skeleton = f"""/**
 * {purpose}
 */

{imports_str}

{exports_str}
"""
        elif file_ext == ".html":
            skeleton = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{purpose}</title>
</head>
<body>
  <!-- {purpose} -->
</body>
</html>
"""
        elif file_ext == ".css":
            skeleton = f"""/* {purpose} */

/* TODO: Add styles */
"""
        else:
            skeleton = f"""/* {purpose} */
TODO: Implement {file_path}
"""

        return skeleton

    def edit_existing_file(
        self,
        file_path: str,
        current_content: str,
        readme: str,
        issues_to_fix: List[Dict] = None,
        edit_strategy: str = "partial",
    ) -> str:
        """
        Edit an existing file with targeted improvements. Delegates to CodePatcher.

        Args:
            file_path: Path to the file to edit
            current_content: Current content of the file
            readme: Project README for context
            issues_to_fix: Specific issues to address
            edit_strategy: "partial" for selective edits, "merge" to merge with full rewrite

        Returns:
            Updated file content
        """
        return self._code_patcher.edit_existing_file(file_path, current_content, readme, issues_to_fix, edit_strategy)
