"""Code patching and merging utilities using structured diff strategies.

Extraído de EnhancedFileContentGenerator para cumplir el Principio de
Responsabilidad Única (SRP). Este módulo se encarga exclusivamente de
editar y fusionar archivos existentes; la creación desde cero corresponde
a EnhancedFileContentGenerator.
"""

import difflib
import re as _re_patch
import textwrap
from typing import Dict, List, Optional, Tuple

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
        elif edit_strategy == "search_replace":
            return self._apply_search_replace_strategy(file_path, current_content, readme, issues_to_fix)
        else:
            return current_content

    # ------------------------------------------------------------------
    # F6: SEARCH/REPLACE patch utilities
    # ------------------------------------------------------------------

    @staticmethod
    def parse_search_replace_patch(text: str) -> List[Tuple[str, str]]:
        """Parse SEARCH/REPLACE blocks from raw LLM output.

        Expected format per block::

            <<<SEARCH>>>
            <exact text to find>
            <<<REPLACE>>>
            <replacement text>
            <<<END>>>

        Args:
            text: Raw LLM response text.

        Returns:
            List of ``(search_block, replace_block)`` tuples.
            Returns an empty list if no valid blocks are found.
        """
        pattern = _re_patch.compile(
            r"<<<SEARCH>>>\n(.*?)<<<REPLACE>>>\n(.*?)<<<END>>>",
            _re_patch.DOTALL,
        )
        return [(m.group(1), m.group(2)) for m in pattern.finditer(text)]

    def apply_unique_edit(
        self,
        file_content: str,
        old_string: str,
        new_string: str,
    ) -> Tuple[str, List[str]]:
        """Replace *old_string* with *new_string* with strict uniqueness validation.

        Unlike :meth:`apply_search_replace`, this method:

        * Validates that *old_string* appears **exactly once** in the file.
        * Normalises leading whitespace before matching so minor indentation
          differences do not silently fail.
        * Returns a unified-diff alongside the updated content so callers can
          show a preview before persisting.

        Args:
            file_content: Current content of the file.
            old_string: Exact text to find (must be unique).
            new_string: Replacement text.

        Returns:
            ``(new_content, diff_lines)`` where *diff_lines* is a list of
            strings produced by :func:`difflib.unified_diff`.

        Raises:
            ValueError: If *old_string* is not found or appears more than once.
        """
        import textwrap

        count = file_content.count(old_string)

        if count == 0:
            # Try normalised (dedented) version to give a better error message
            normalised_old = textwrap.dedent(old_string).strip()
            normalised_content = textwrap.dedent(file_content)
            if normalised_old not in normalised_content:
                # Find the closest 5-line window in the file for the error message
                content_preview = file_content[:500] + ("..." if len(file_content) > 500 else "")
                diff = list(
                    difflib.unified_diff(
                        [content_preview],
                        [old_string],
                        fromfile="file (excerpt)",
                        tofile="expected old_string",
                        lineterm="",
                    )
                )
                raise ValueError(
                    "old_string not found in file. "
                    "Make sure the text matches exactly (including indentation).\n" + "\n".join(diff[:20])
                )
            # Normalised match found — use it directly
            new_content = normalised_content.replace(normalised_old, new_string, 1)
        elif count > 1:
            # Report line numbers of all occurrences to help the caller disambiguate
            lines = file_content.splitlines()
            hits = [i + 1 for i, line in enumerate(lines) if old_string.splitlines()[0] in line]
            raise ValueError(
                f"old_string appears {count} times in the file "
                f"(first-line matches near lines {hits}). "
                f"Add more surrounding context to make it unique."
            )
        else:
            new_content = file_content.replace(old_string, new_string, 1)

        diff = list(
            difflib.unified_diff(
                file_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="a/original",
                tofile="b/modified",
                lineterm="",
            )
        )
        self.logger.info(
            f"  apply_unique_edit: {len(old_string)} chars → {len(new_string)} chars ({len(diff)} diff lines)"
        )
        return new_content, diff

    def apply_search_replace(
        self,
        file_content: str,
        patches: List[Tuple[str, str]],
    ) -> Tuple[str, List[str]]:
        """Apply a list of ``(search, replace)`` patches to *file_content*.

        Each SEARCH block must appear verbatim in the file. Patches where the
        SEARCH text is not found are skipped and recorded in *failed*.

        Args:
            file_content: Current file text.
            patches: List of ``(search_block, replace_block)`` pairs.

        Returns:
            ``(modified_content, failed_search_blocks)`` where
            *failed_search_blocks* contains SEARCH strings that were not found.
        """
        result = file_content
        failed: List[str] = []
        for search, replace in patches:
            if search in result:
                result = result.replace(search, replace, 1)
                self.logger.info(f"  SEARCH/REPLACE applied: {len(search)} chars -> {len(replace)} chars")
            else:
                # Fallback: try dedent-normalised match (handles indent differences)
                norm_search = textwrap.dedent(search).strip()
                norm_result = textwrap.dedent(result)
                if norm_search and norm_search in norm_result:
                    norm_replace = textwrap.dedent(replace).strip()
                    result = norm_result.replace(norm_search, norm_replace, 1)
                    self.logger.info(
                        f"  SEARCH/REPLACE applied (dedent-normalized): "
                        f"{len(search)} chars -> {len(replace)} chars"
                    )
                else:
                    self.logger.warning(
                        f"  SEARCH block not found in file ({len(search)} chars). Skipping patch."
                    )
                    failed.append(search)
        return result, failed

    def _apply_search_replace_strategy(
        self,
        file_path: str,
        current_content: str,
        readme: str,
        issues_to_fix: Optional[List[Dict]] = None,
    ) -> str:
        """Prompt the LLM for SEARCH/REPLACE patches and apply them safely.

        Falls back to *current_content* if no valid blocks are produced or an
        error occurs — ensuring the file is never left in a broken state.
        """
        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = loader.load_prompt_sync("domains/auto_generation/code_repair.yaml")
            system = prompts.get("search_replace_edit", {}).get("system", "")
            user_template = prompts.get("search_replace_edit", {}).get("user", "")
            issues_str = "\n".join(f"- {i.get('description', '')}" for i in (issues_to_fix or []))
            user = user_template.format(
                file_path=file_path,
                current_content=current_content[:12000],
                issues=issues_str or "General improvement",
                readme=readme[:300],
            )
            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[],
                options_override={"temperature": 0.1, "think": False},
            )
            raw = response_data.get("content", "")
            patches = self.parse_search_replace_patch(raw)
            if not patches:
                self.logger.warning(f"  No SEARCH/REPLACE blocks found for {file_path}")
                return current_content
            modified, failed = self.apply_search_replace(current_content, patches)
            if failed:
                self.logger.warning(f"  {len(failed)}/{len(patches)} patches failed for {file_path}")
            return modified
        except Exception as e:
            self.logger.error(f"SEARCH/REPLACE strategy failed for {file_path}: {e}")
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

            improved_content_raw = response_data.get("content", "")
            improved_content = self.response_parser.extract_code(improved_content_raw, file_path)
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
            self.logger.warning(f"Improved version similarity {similarity:.2f} is too low — keeping original")
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
        """Find the section of code that matches the problem description.

        Tries line-number extraction first (works for all ruff/tsc/linter errors),
        then falls back to keyword search with an expanded window.
        """
        lines = content.split("\n")

        # 1. Extract line number from error message (e.g. "line 42" or "(line 42)")
        line_match = _re_patch.search(r"\bline\s+(\d+)\b", issue_desc, _re_patch.IGNORECASE)
        if not line_match:
            # Also try colon-separated format: "file.py:42:5: E501 ..."
            line_match = _re_patch.search(r":(\d+):\d+:", issue_desc)
        if line_match:
            lineno = int(line_match.group(1)) - 1  # convert to 0-indexed
            start = max(0, lineno - 3)
            end = min(len(lines), lineno + 6)
            return "\n".join(lines[start:end])

        # 2. Keyword fallback with expanded window (18 lines instead of 5)
        keywords = [k for k in issue_desc.lower().split()[:5] if len(k) > 3]
        best_start = -1
        best_count = 0
        for i, line in enumerate(lines):
            count = sum(1 for kw in keywords if kw in line.lower())
            if count > best_count:
                best_count = count
                best_start = i

        if best_start >= 0:
            start = max(0, best_start - 2)
            end = min(len(lines), best_start + 16)
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
                options_override={"temperature": 0.15, "think": False},
            )

            fixed_raw = response_data.get("content", "")
            fixed = self.response_parser.extract_code(fixed_raw, file_path)
            return fixed.strip()

        except Exception as e:
            self.logger.warning(f"Could not generate fix: {e}")
            return problem_section

    def inject_missing_function(self, file_path: str, content: str, requirement: str, related_context: str = "") -> str:
        """Inject a missing function or method into the code using centralized prompts."""
        self.logger.info(f"  Injecting missing logic for '{requirement}' into {file_path}...")

        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = loader.load_prompt_sync("domains/auto_generation/code_repair.yaml")

            system = prompts.get("surgical_injection", {}).get("system", "")
            user_template = prompts.get("surgical_injection", {}).get("user", "")

            # Fix: match keys in code_repair.yaml (injection_data, file_content)
            user = user_template.format(
                file_path=file_path,
                injection_data=requirement,
                file_content=content,
                related_context=related_context or "(No additional context provided)",
            )

            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[],
                options_override={"temperature": 0.1, "think": False},
            )

            new_content = self.response_parser.extract_code(response_data.get("content", ""), file_path)
            return new_content if new_content and len(new_content) > len(content) else content
        except Exception as e:
            self.logger.error(f"Injection failed: {e}")
            return content

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
