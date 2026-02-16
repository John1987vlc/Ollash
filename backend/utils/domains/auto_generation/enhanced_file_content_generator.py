"""Enhanced File Content Generator that uses logic plans for better implementation."""

from pathlib import Path
from typing import Any, Dict, List

from backend.services.llm_manager import OllamaClient
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser


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

                self.logger.warning(f"  Attempt {attempt + 1}: Generated content failed validation")

            except Exception as e:
                self.logger.error(f"  Attempt {attempt + 1} failed: {e}")

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
## File to Generate: {file_path}

### Purpose
{purpose}

### What to Export (Functions/Classes/Variables)
{chr(10).join(f"- {e}" for e in exports)}

### Required Imports
{chr(10).join(f"- {i}" for i in imports) if imports else "None (if internal only)"}

### Main Implementation Logic (Step by step)
{chr(10).join(f"{i + 1}. {logic}" for i, logic in enumerate(main_logic))}

### Dependencies on Other Files
{chr(10).join(f"- {d}" for d in dependencies) if dependencies else "None"}

### Related Project Files for Context
{self._format_related_files(related_files)}

### Project README
{readme[:500]}...

### Validation Criteria
{chr(10).join(f"- {v}" for v in validation)}

## Instructions
1. Generate COMPLETE, working code
2. Include ALL necessary imports
3. Implement EVERY export listed above
4. Follow the step-by-step logic
5. Make code production-ready
6. Add helpful comments for complex logic
"""
        return context

    def _format_related_files(self, related_files: Dict[str, str]) -> str:
        """Format related files for context."""
        if not related_files:
            return "None"

        lines = []
        for path, content in related_files.items():
            # Show first 200 chars of each related file
            preview = content[:200].replace("\n", " ")
            lines.append(f"- {path}: {preview}...")

        return "\n".join(lines)

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
        if file_ext in [".py", ".js", ".ts", ".java", ".go", ".rb"]:
            system_prompt = self._get_code_generation_system_prompt(file_ext)
        else:
            system_prompt = "Generate complete, production-ready content."

        user_prompt = f"""{context}

## Your Task
Generate the COMPLETE content for {file_path}.

Requirements:
1. Every export must be fully implemented
2. Every import must be included
3. No TODOs or placeholders
4. Ready to run/use immediately
5. Well-commented where needed

Generate ONLY the file content, no explanations."""

        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Lower for more deterministic code
        )

        return response_data.get("content", "")

    def _get_code_generation_system_prompt(self, file_ext: str) -> str:
        """Get language-specific system prompt."""

        prompts = {
            ".py": """You are an expert Python developer. Generate clean, production-ready Python code.
- Follow PEP 8 style guide
- Include docstrings for functions
- Use type hints
- Handle errors appropriately
- Make code complete and functional""",
            ".js": """You are an expert JavaScript developer. Generate clean, production-ready JavaScript code.
- Use modern ES6+ syntax
- Follow consistent naming conventions
- Include comments for complex logic
- Make code complete and functional
- No console errors or warnings""",
            ".ts": """You are an expert TypeScript developer. Generate clean, production-ready TypeScript code.
- Use proper type annotations
- Follow best practices
- Include JSDoc comments
- Make code complete and functional""",
            ".html": """You are an expert HTML/CSS developer. Generate clean, semantic HTML.
- Use semantic HTML5 elements
- Proper accessibility attributes
- Clean, readable structure
- Include necessary styling""",
            ".css": """You are an expert CSS developer. Generate clean, maintainable CSS.
- Use modern CSS features
- Responsive design
- Comments for complex selectors
- Organized and reusable""",
        }

        return prompts.get(
            file_ext,
            "You are a code generation expert. Generate production-ready content.",
        )

    def _validate_content(self, content: str, file_path: str, exports: List[str], validation: List[str]) -> bool:
        """Validate that generated content meets requirements."""

        if not content or len(content.strip()) < 20:
            self.logger.warning(f"  Content too short for {file_path}")
            return False

        file_ext = Path(file_path).suffix

        # Check for required exports
        for export in exports:
            # Simple heuristic: check if export name appears in content
            if export not in content:
                self.logger.warning(f"  Missing export '{export}' in {file_path}")
                return False

        # Language-specific validation
        if file_ext == ".py":
            # Check for unmatched brackets
            if content.count("(") != content.count(")"):
                self.logger.warning(f"  Unmatched parentheses in {file_path}")
                return False

        elif file_ext == ".js":
            # Check for unmatched braces
            if content.count("{") != content.count("}"):
                self.logger.warning(f"  Unmatched braces in {file_path}")
                return False
            # Check for unterminated strings (basic)
            if content.count('"""') % 2 != 0 and content.count("'''") % 2 != 0:
                if content.count('"') % 2 != 0:
                    return False

        # Check that code doesn't have obvious placeholder markers
        placeholders = ["TODO", "FIXME", "XXX", "...", "pass", "return None"]
        placeholder_count = sum(content.count(p) for p in placeholders)

        if placeholder_count > len(exports):  # More placeholders than exports
            self.logger.warning(f"  Too many placeholder markers in {file_path}")
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

        self.logger.info(f"📝 Editing existing {file_path} using {edit_strategy} strategy...")

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

        self.logger.info(f"  🎯 Applying {len(issues_to_fix)} targeted edits...")

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
                    self.logger.info(f"    ✅ Fixed: {issue_desc[:40]}...")

        return edited_content

    def _merge_original_with_improvements(self, file_path: str, current_content: str, readme: str) -> str:
        """
        Generate an improved version and intelligently merge it with the original.
        Preserves custom modifications while applying improvements.
        """

        self.logger.info("  🔀 Merging improvements with existing content...")

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
