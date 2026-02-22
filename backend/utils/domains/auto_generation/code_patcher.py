"""Code patching and merging utilities using structured diff strategies.

Extraído de EnhancedFileContentGenerator para cumplir el Principio de
Responsabilidad Única (SRP). Este módulo se encarga exclusivamente de
editar y fusionar archivos existentes; la creación desde cero corresponde
a EnhancedFileContentGenerator.
"""

import difflib
from typing import Dict, List, Optional

from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser


class CodePatcher:
    """Handles targeted edits and intelligent merging of existing files.

    Uses difflib.SequenceMatcher for structural comparison instead of
    fragile length-ratio or brace-counting heuristics.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: Optional[LLMResponseParser] = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.response_parser = response_parser or LLMResponseParser()

    def edit_existing_file(
        self,
        file_path: str,
        current_content: str,
        readme: str,
        issues_to_fix: Optional[List[Dict]] = None,
        edit_strategy: str = "partial",
    ) -> str:
        """
        Edit an existing file with targeted improvements.

        Args:
            file_path: Path to the file to edit
            current_content: Current content of the file
            readme: Project README for context
            issues_to_fix: Specific issues to address
            edit_strategy: "partial" for selective edits, "merge" for full rewrite merge

        Returns:
            Updated file content
        """
        self.logger.info(f"Editing existing {file_path} using {edit_strategy} strategy...")

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
        """Apply targeted fixes to specific sections without a full rewrite."""

        self.logger.info(f"  Applying {len(issues_to_fix)} targeted edits...")

        edited_content = current_content

        for issue in issues_to_fix[:5]:  # Limit to 5 issues per pass
            issue_desc = issue.get("description", "")

            problem_section = self._find_problem_section(issue_desc, edited_content)

            if problem_section:
                self.logger.info(f"    Found: {issue_desc[:40]}...")

                fix = self._generate_section_fix(file_path, problem_section, issue_desc, readme)

                if fix and fix != problem_section:
                    edited_content = edited_content.replace(problem_section, fix, 1)
                    self.logger.info(f"    Fixed: {issue_desc[:40]}...")

        return edited_content

    def _merge_original_with_improvements(self, file_path: str, current_content: str, readme: str) -> str:
        """Generate an improved version and intelligently merge it with the original."""

        self.logger.info("  Merging improvements with existing content...")

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
                tools=[],
                options_override={"temperature": 0.2},
            )

            improved_content = response_data.get("content", "")
            return self._smart_merge(current_content, improved_content)

        except Exception as e:
            self.logger.warning(f"Merge failed: {e}")
            return current_content

    def _smart_merge(self, original: str, improved: str) -> str:
        """Merge original and improved versions using difflib.SequenceMatcher.

        Replaces the previous fragile heuristics (length ratios, brace counting)
        with a structural diff-based approach.

        Rules:
        - If improved is empty or too short, keep original.
        - If similarity < 30%, improved is suspiciously different — keep original.
        - If similarity > 70%, improved is close enough — use improved directly.
        - Otherwise perform a line-level opcode merge.
        """
        if not improved or len(improved.strip()) < 20:
            return original

        matcher = difflib.SequenceMatcher(None, original, improved, autojunk=False)
        similarity = matcher.ratio()

        if similarity < 0.30:
            self.logger.warning(
                f"Improved version similarity {similarity:.2f} is too low — keeping original"
            )
            return original

        if similarity > 0.70:
            return improved

        # Moderate similarity: perform opcode-based line merge
        original_lines = original.splitlines()
        improved_lines = improved.splitlines()
        line_matcher = difflib.SequenceMatcher(None, original_lines, improved_lines, autojunk=False)

        result: List[str] = []
        for tag, i1, i2, j1, j2 in line_matcher.get_opcodes():
            if tag == "equal":
                result.extend(original_lines[i1:i2])
            elif tag == "replace":
                # Prefer the improved replacement
                result.extend(improved_lines[j1:j2])
            elif tag == "insert":
                result.extend(improved_lines[j1:j2])
            elif tag == "delete":
                # Keep deleted original lines so we never silently lose code
                result.extend(original_lines[i1:i2])

        return "\n".join(result)

    def _find_problem_section(self, issue_desc: str, content: str) -> str:
        """Find the section of code that matches the problem description."""

        keywords = issue_desc.lower().split()[:3]
        lines = content.split("\n")

        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword in line.lower():
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
                tools=[],
                options_override={"temperature": 0.15},
            )

            fixed = response_data.get("content", "")
            return fixed.strip()

        except Exception as e:
            self.logger.warning(f"Could not generate fix: {e}")
            return problem_section

    def _is_better_line(self, orig: str, improved: str) -> bool:
        """Determine if the improved line is better using content analysis.

        Replaces the old brace/parenthesis counting heuristic with a
        difflib similarity + content-length comparison.
        """
        if not improved or not orig:
            return False

        # Fewer TODOs is always better
        if improved.lower().count("todo") < orig.lower().count("todo"):
            return True

        # Similar lines where improved has more meaningful content
        ratio = difflib.SequenceMatcher(None, orig.strip(), improved.strip()).ratio()
        if ratio > 0.6 and len(improved.strip()) > len(orig.strip()):
            return True

        return False
