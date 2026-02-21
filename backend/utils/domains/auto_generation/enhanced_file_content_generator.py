"""Enhanced File Content Generator that uses logic plans for better implementation."""

from pathlib import Path
from typing import Any, Dict, List

from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser


class EnhancedFileContentGenerator:
    """
    Improved file content generator that:
    1. Uses detailed implementation plans from LogicPlanningPhase
    2. Validates content incrementally
    3. Handles partial/incomplete file generation with retry
    4. Breaks large functions into smaller chunks
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.response_parser = response_parser or LLMResponseParser()
        self.max_retries = 3

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
        """Build detailed context for file generation."""

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
        return context

    def _generate_with_prompt(
        self,
        file_path: str,
        context: str,
        purpose: str,
        exports: List[str],
        main_logic: List[str],
        validation: List[str],
    ) -> str:
        """Generate file content with specialized prompt."""

        file_ext = Path(file_path).suffix

        # Use appropriate language/format prompt
        system_prompt = self._get_code_generation_system_prompt(file_ext)

        user_prompt = f"""{context}

Generate the COMPLETE content for {file_path}.
1. Implement EVERY export.
2. Include ALL necessary imports.
3. NO TODOs or placeholders.
4. Production-ready, functional code.

Output ONLY the code content."""

        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options_override={"temperature": 0.2},  # More deterministic
        )

        content = response_data["message"]["content"]
        # Use parser to clean up markdown if any
        return self.response_parser.extract_code_block(content) or content

    def _get_code_generation_system_prompt(self, file_ext: str) -> str:
        """Get language-specific system prompt."""

        base = "You are an expert developer. Generate COMPLETE, production-ready code with no placeholders or TODOs. Return ONLY the code."

        prompts = {
            ".py": base + " Follow PEP 8, use type hints, and include docstrings.",
            ".js": base + " Use modern ES6+ syntax and follow best practices.",
            ".ts": base + " Use strict type annotations and interfaces.",
            ".html": base + " Use semantic HTML5 and accessible structure.",
            ".css": base + " Use modern features and responsive design.",
        }

        return prompts.get(file_ext, base)

    def _validate_content(self, content: str, file_path: str, exports: List[str], validation: List[str]) -> bool:
        """Validate that generated content meets requirements."""

        if not content or len(content.strip()) < 20:
            self.logger.warning(f"  Content too short for {file_path}")
            return False

        file_ext = Path(file_path).suffix
        import re

        # Check for required exports with word boundaries to avoid false positives in comments/docstrings
        for export in exports:
            clean_export = export.replace("()", "").strip()
            # Search for the export name as a whole word (e.g., not matching 'main' inside 'main_logic')
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
            # Check for skeleton characteristics
            lines = content.strip().split("\n")
            pass_count = content.count("pass")
            if pass_count > len(exports) and len(lines) < 10:
                self.logger.warning(f"  Skeleton detected (too many pass statements) for {file_path}")
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
        Edit an existing file with targeted improvements instead of full rewrite.

        Args:
            file_path: Path to the file to edit
            current_content: Current content of the file
            readme: Project README for context
            issues_to_fix: Specific issues to address
            edit_strategy: "partial" for selective edits, "merge" to merge with full rewrite

        Returns:
            Updated file content
        """

        self.logger.info(f"ðŸ“ Editing existing {file_path} using {edit_strategy} strategy...")

        if not current_content:
            return ""

        if edit_strategy == "partial" and issues_to_fix:
            return self._apply_partial_edits(file_path, current_content, readme, issues_to_fix)
        elif edit_strategy == "merge":
            return self._merge_original_with_improvements(file_path, current_content, readme)
        else:
            return current_content

    def _apply_partial_edits(
        self,
        file_path: str,
        current_content: str,
        readme: str,
        issues_to_fix: List[Dict],
    ) -> str:
        """
        Apply targeted fixes to specific sections of a file without full rewrite.
        """

        self.logger.info(f"  ðŸŽ¯ Applying {len(issues_to_fix)} targeted edits...")

        edited_content = current_content

        for issue in issues_to_fix[:5]:  # Limit to 5 issues per pass
            issue_desc = issue.get("description", "")

            # Find the problematic section
            problem_section = self._find_problem_section(issue_desc, edited_content)

            if problem_section:
                self.logger.info(f"    Found: {issue_desc[:40]}...")

                # Generate fix for this section
                fix = self._generate_section_fix(file_path, problem_section, issue_desc, readme)

                if fix and fix != problem_section:
                    edited_content = edited_content.replace(problem_section, fix, 1)
                    self.logger.info(f"    âœ… Fixed: {issue_desc[:40]}...")

        return edited_content

    def _merge_original_with_improvements(self, file_path: str, current_content: str, readme: str) -> str:
        """
        Generate an improved version and intelligently merge it with the original.
        Preserves custom modifications while applying improvements.
        """

        self.logger.info("  ðŸ”€ Merging improvements with existing content...")

        # Generate improved version
        improved_prompt = f"""Improve this {file_path} while keeping all existing logic:

CURRENT CODE:
```
{current_content}
```

PROJECT CONTEXT:
{readme[:300]}

Improvements to make:
- Better error handling
- Improved clarity and organization
- More complete implementation
- Better following of conventions

Output the improved version only, no explanations."""

        try:
            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a code improvement expert."},
                    {"role": "user", "content": improved_prompt},
                ],
                temperature=0.2,
            )

            improved_content = response_data.get("content", "")

            # Intelligently merge: use improved version but preserve custom sections
            return self._smart_merge(current_content, improved_content)

        except Exception as e:
            self.logger.warning(f"Merge failed: {e}")
            return current_content

    def _smart_merge(self, original: str, improved: str) -> str:
        """
        Intelligently merge original and improved versions.
        Keeps original structure but uses improved implementations.
        """

        # If improved is substantially larger, it's likely better
        if len(improved) > len(original) * 0.8 and len(improved) < len(original) * 1.5:
            return improved

        # Otherwise keep original but look for specific improvements
        lines_orig = original.split("\n")
        lines_improved = improved.split("\n")

        result_lines = []

        for i, orig_line in enumerate(lines_orig):
            if i < len(lines_improved):
                improved_line = lines_improved[i]
                # Use improved line if it's a meaningful improvement
                if self._is_better_line(orig_line, improved_line):
                    result_lines.append(improved_line)
                else:
                    result_lines.append(orig_line)
            else:
                result_lines.append(orig_line)

        # Append any additional lines from improved version
        if len(lines_improved) > len(lines_orig):
            result_lines.extend(lines_improved[len(lines_orig) :])

        return "\n".join(result_lines)

    def _find_problem_section(self, issue_desc: str, content: str) -> str:
        """Find the section of code that matches the problem description."""

        # Extract keywords from issue
        keywords = issue_desc.lower().split()[:3]

        lines = content.split("\n")

        # Find line(s) containing keywords
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword in line.lower():
                    # Return a small context around the problem
                    start = max(0, i - 1)
                    end = min(len(lines), i + 3)
                    return "\n".join(lines[start:end])

        return ""

    def _generate_section_fix(self, file_path: str, problem_section: str, issue_desc: str, readme: str) -> str:
        """Generate a fix for a specific section."""

        fix_prompt = f"""Fix this specific issue in {file_path}:

ISSUE: {issue_desc}

PROBLEMATIC CODE:
```
{problem_section}
```

PROJECT CONTEXT:
{readme[:200]}

Generate ONLY the fixed code (same language), no explanations."""

        try:
            response_data, _ = self.llm_client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a code fixer. Fix issues precisely.",
                    },
                    {"role": "user", "content": fix_prompt},
                ],
                temperature=0.15,
            )

            fixed = response_data.get("content", "")
            return fixed.strip()

        except Exception as e:
            self.logger.warning(f"Could not generate fix: {e}")
            return problem_section

    def _is_better_line(self, orig: str, improved: str) -> bool:
        """Determine if the improved line is actually better."""

        if not improved or not orig:
            return False

        # Improved line is better if it's longer and has more substance
        if len(improved) > len(orig) and improved.count("{") + improved.count("(") > orig.count("{") + orig.count("("):
            return True

        # Or if it has less "TODO" markers
        orig_todos = orig.lower().count("todo")
        improved_todos = improved.lower().count("todo")

        if improved_todos < orig_todos:
            return True

        # Or if it has more comments/documentation
        if improved.count("#") + improved.count("//") + improved.count('"""') > orig.count("#") + orig.count(
            "//"
        ) + orig.count('"""'):
            return True

        return False

    def _validate_content(self, content: str, file_path: str, exports: List[str], validation: List[str]) -> bool:
        """Validate that generated content meets requirements."""

        if not content or len(content.strip()) < 20:
            self.logger.warning(f"  Content too short for {file_path}")
            return False

        file_ext = Path(file_path).suffix

        # Check for required exports
        for export in exports:
            # Simple heuristic: check if export name appears in content
            # Remove parentheses if it's a function call in the plan
            clean_export = export.replace("()", "").strip()
            # F35: More strict check for export presence (look for word boundary)
            import re

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
            if (content.count("pass") + content.count("...")) > len(exports) and len(content.strip().split("\n")) < 10:
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
