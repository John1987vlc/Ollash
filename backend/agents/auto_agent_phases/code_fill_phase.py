"""Phase 4: CodeFillPhase — core file content generation.

Processes files in priority order (set by BlueprintPhase).
Per-file token budget:
  System prompt:      ~800 tokens  (role + rules)
  Plan entry:         ~200 tokens  (path/purpose/exports/imports/key_logic)
  Signature context:  ~500 tokens  (signatures of max 3 dependency files)
  Previous summary:   ~300 tokens  (last generated file — coherence anchor)
  Generation:        ~2000 tokens
  Total:             ~3800 tokens  (fits in 4K window)

Non-code files (JSON, YAML, MD, .env, etc.) use a lightweight config prompt.
Python files are syntax-validated immediately; one retry on failure.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext

_NON_CODE_EXTS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".env",
    ".gitignore",
    ".cfg",
    ".ini",
    ".lock",
}

_SYSTEM_FULL = """# ROLE
Expert {language} developer. Generate complete, functional source code.

# RULES
- FORBIDDEN: TODO comments, pass (unless abstract method), ..., raise NotImplementedError, placeholder comments like "# implement this"
- Write real, working implementations
- Follow {language} idioms and best practices
- Use type hints / type annotations everywhere
- Output ONLY the file content. No explanations. No markdown fences."""

_SYSTEM_SMALL = """# ROLE
{language} developer. Write working code.

# RULES
- No TODO, no placeholders, no pass with empty body
- Output code only — no explanations, no markdown"""

_USER_FULL = """## FILE TO GENERATE
Path: {file_path}
Purpose: {purpose}
Public exports: {exports}
Depends on files: {imports}
Key implementation: {key_logic}

## DEPENDENCY SIGNATURES (from already-generated files)
{signature_context}

## PREVIOUSLY GENERATED
{previous_summary}

Write the complete content of `{file_path}` now:"""

_USER_SMALL = """File: {file_path}
Purpose: {purpose}
Depends on: {imports}
Key logic: {key_logic}

{signature_context}

Write {file_path}:"""

_CONFIG_SYSTEM = "Generate the content of the requested config/doc file. Output only the file content."

_CONFIG_USER = """File: {file_path}
Purpose: {purpose}
Project type: {project_type}
Tech stack: {tech_stack}
Key logic / content: {key_logic}

Write {file_path}:"""


class CodeFillPhase(BasePhase):
    phase_id = "4"
    phase_label = "Code Fill"

    def run(self, ctx: PhaseContext) -> None:
        is_small = ctx.is_small()
        system_tmpl = _SYSTEM_SMALL if is_small else _SYSTEM_FULL
        user_tmpl = _USER_SMALL if is_small else _USER_FULL

        previous_summary = ""
        generated_count = 0
        failure_count = 0

        for plan in ctx.blueprint:  # already sorted by priority
            if self._is_non_code(plan.path):
                self._generate_config(ctx, plan)
                continue

            language = self._detect_language(plan.path)
            sig_context = self._build_signature_context(ctx, plan)
            system = system_tmpl.format(language=language)

            if is_small:
                user = user_tmpl.format(
                    file_path=plan.path,
                    purpose=plan.purpose,
                    imports=", ".join(plan.imports) or "none",
                    key_logic=plan.key_logic or "implement as described",
                    signature_context=sig_context,
                )
            else:
                user = user_tmpl.format(
                    file_path=plan.path,
                    purpose=plan.purpose,
                    exports=", ".join(plan.exports) or "none",
                    imports=", ".join(plan.imports) or "none",
                    key_logic=plan.key_logic or "implement as described",
                    signature_context=sig_context,
                    previous_summary=previous_summary[:300],
                )

            content = self._generate_with_retry(ctx, system, user, plan)

            if content:
                self._write_file(ctx, plan.path, content)
                generated_count += 1
                previous_summary = f"Last: {plan.path} — {plan.purpose}"
                ctx.logger.info(f"  [CodeFill] {plan.path} ({len(content)} chars)")
            else:
                ctx.errors.append(f"CodeFill: failed to generate {plan.path}")
                failure_count += 1

        ctx.metrics["code_fill_generated"] = generated_count
        ctx.metrics["code_fill_failures"] = failure_count
        ctx.logger.info(f"[CodeFill] {generated_count} files generated, {failure_count} failures")

    # ----------------------------------------------------------------
    # Generation helpers
    # ----------------------------------------------------------------

    def _generate_with_retry(
        self,
        ctx: PhaseContext,
        system: str,
        user: str,
        plan: FilePlan,
    ) -> Optional[str]:
        """Try to generate file content. One retry on syntax error."""
        current_user = user
        for attempt in range(2):
            raw = self._llm_call(ctx, system, current_user, role="coder")
            content = self._extract_code(raw, plan.path)

            if content and self._validate_syntax(plan.path, content):
                return content

            if attempt == 0:
                lang = self._detect_language(plan.path)
                ctx.logger.warning(f"  [CodeFill] Syntax issue in {plan.path}, retrying...")
                current_user = (
                    user + f"\n\nPREVIOUS ATTEMPT HAD ISSUES. Write clean, valid {lang} code. No placeholders."
                )

        # Return best-effort content even if syntax check fails
        return self._extract_code(self._llm_call(ctx, system, current_user, role="coder"), plan.path)

    def _build_signature_context(self, ctx: PhaseContext, plan: FilePlan) -> str:
        """Return signature-only content of dependency files. Budget: ~500 tokens (~2000 chars)."""
        try:
            from backend.utils.domains.auto_generation.utilities.signature_extractor import (
                extract_signatures,
            )
        except ImportError:
            return "No signature extractor available."

        lines: List[str] = []
        chars_used = 0
        char_budget = 2000  # 500 tokens * 4 chars/token

        for dep_path in plan.imports[:3]:  # max 3 dependencies
            content = ctx.generated_files.get(dep_path, "")
            if not content:
                continue
            sigs = extract_signatures(content, dep_path)
            chunk = f"# From {dep_path}:\n{sigs}\n"
            if chars_used + len(chunk) > char_budget:
                break
            lines.append(chunk)
            chars_used += len(chunk)

        return "\n".join(lines) or "No dependency signatures available yet."

    def _generate_config(self, ctx: PhaseContext, plan: FilePlan) -> None:
        """Generate config/doc files with a minimal dedicated prompt."""
        # Special case: README.md generated by blueprint phase already
        if plan.path == "README.md" and plan.path in ctx.generated_files:
            return

        user = _CONFIG_USER.format(
            file_path=plan.path,
            purpose=plan.purpose,
            project_type=ctx.project_type,
            tech_stack=", ".join(ctx.tech_stack),
            key_logic=plan.key_logic or "standard content for this file type",
        )
        content = self._llm_call(ctx, _CONFIG_SYSTEM, user, role="coder")
        if content:
            self._write_file(ctx, plan.path, content.strip())

    # ----------------------------------------------------------------
    # Validation / extraction helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _validate_syntax(file_path: str, content: str) -> bool:
        """Syntax check for Python files. Other languages pass."""
        if Path(file_path).suffix.lower() == ".py":
            try:
                ast.parse(content)
                return True
            except SyntaxError:
                return False
        return True

    @staticmethod
    def _extract_code(raw: str, file_path: str) -> str:
        """Extract code from LLM response (fenced or unfenced)."""
        try:
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser

            block = LLMResponseParser.extract_code_block_for_file(raw, file_path)
            return block.strip() if block else raw.strip()
        except Exception:
            return raw.strip()

    @staticmethod
    def _is_non_code(path: str) -> bool:
        ext = Path(path).suffix.lower()
        name = Path(path).name.lower()
        return ext in _NON_CODE_EXTS or name in {"dockerfile", "makefile", "procfile"}

    @staticmethod
    def _detect_language(path: str) -> str:
        try:
            from backend.utils.core.language_utils import LanguageUtils

            return LanguageUtils.infer_language(path)
        except Exception:
            ext_map = {
                ".py": "Python",
                ".ts": "TypeScript",
                ".tsx": "TypeScript",
                ".js": "JavaScript",
                ".jsx": "JavaScript",
                ".go": "Go",
                ".rs": "Rust",
                ".java": "Java",
                ".cs": "C#",
                ".cpp": "C++",
            }
            return ext_map.get(Path(path).suffix.lower(), "Python")
